"""HTTP client for the Irving Energy residential account portal.

The portal is a server rendered Apache/PHP application. A ``requests.Session``
is kept for the lifetime of the config entry so the session cookie survives
between polls, and every blocking call runs in the Home Assistant executor.
Credentials are only placed in the login POST body: they are never logged and
never included in exception messages.
"""

import logging
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from homeassistant.core import HomeAssistant

from .const import (
    BASE_URL,
    LOGIN_FIELD_EMAIL,
    LOGIN_FIELD_PASSWORD,
    LOGIN_FIELD_SUBMIT,
    LOGIN_URL,
    MFA_MARKERS,
    REQUEST_TIMEOUT,
    USER_AGENT,
    USER_HOME_URL,
)
from .parser import is_login_page, to_soup

_LOGGER = logging.getLogger(__name__)

_LOGIN_PATHS = frozenset(
    {"", "/", "/index.php", "/login", "/login.php", "/signin", "/signin.php"}
)


class MyIrvingError(Exception):
    """Raised when the portal cannot be reached or returns an unusable page."""


class MyIrvingAuthError(MyIrvingError):
    """Raised when the portal rejects the credentials or requires MFA."""


class MyIrvingClient:
    """Small synchronous portal client wrapped for async Home Assistant use."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        timeout: int = REQUEST_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        """Store the credentials needed for login and re-login."""
        self._hass = hass
        self._username = username
        # The password has to stay in memory so an expired session can be
        # renewed without user interaction. It is never logged or persisted.
        self._password = password
        self._timeout = timeout
        self._session = session
        self._logged_in = False

    def __repr__(self) -> str:
        """Return a representation that never exposes the password or the account."""
        return "<MyIrvingClient username=***>"

    async def async_get_user_home(self) -> BeautifulSoup:
        """Return the parsed /user-home page, logging in again if the session expired.

        The page is parsed once in the executor; callers reuse the returned tree
        instead of parsing the same HTML again.
        """
        return await self._hass.async_add_executor_job(self._get_user_home)

    async def async_close(self) -> None:
        """Close the underlying requests session in the executor."""
        if self._session is not None:
            await self._hass.async_add_executor_job(self._close_session)

    def _close_session(self) -> None:
        """Close the session and forget that it was authenticated."""
        if self._session is not None:
            self._session.close()
            self._session = None
        self._logged_in = False

    def _get_user_home(self) -> BeautifulSoup:
        """Fetch /user-home, retrying once after a fresh login on session expiry."""
        session = self._ensure_session()

        if not self._logged_in:
            self._login(session)

        response = self._request(session, USER_HOME_URL)
        soup = to_soup(response.text)

        if self._session_expired(response, soup):
            _LOGGER.info("MyIrving session expired, re-authenticating")
            self._logged_in = False
            self._login(session)
            response = self._request(session, USER_HOME_URL)
            soup = to_soup(response.text)
            if self._session_expired(response, soup):
                raise MyIrvingAuthError(
                    "The portal session is still logged out after re-authentication"
                )

        if _looks_like_mfa(soup):
            raise MyIrvingAuthError(
                "Multi-factor authentication is not supported by this integration"
            )

        return soup

    def _login(self, session: requests.Session) -> None:
        """Log in with a freshly scraped form so the per-session CSRF token is valid."""
        self._logged_in = False

        login_page = self._request(session, LOGIN_URL)
        login_soup = to_soup(login_page.text)
        form = _find_login_form(login_soup)
        if form is None:
            if _looks_like_mfa(login_soup):
                raise MyIrvingAuthError(
                    "Multi-factor authentication is not supported by this integration"
                )
            raise MyIrvingError(
                "Could not find the login form on the Irving Energy portal"
            )

        payload: dict[str, str] = _hidden_values(form)
        payload[LOGIN_FIELD_EMAIL] = self._username
        payload[LOGIN_FIELD_PASSWORD] = self._password
        payload[LOGIN_FIELD_SUBMIT] = _submit_value(form)

        action = _form_action(form)
        response = self._request(
            session, action, method="post", data=payload, referer=LOGIN_URL
        )
        response_soup = to_soup(response.text)

        if _looks_like_mfa(response_soup):
            raise MyIrvingAuthError(
                "Multi-factor authentication is not supported by this integration"
            )
        if is_login_page(response_soup) or _is_login_url(response.url):
            raise MyIrvingAuthError(
                "The Irving Energy portal rejected the email address or password"
            )

        # The POST response is not guaranteed to be the account home page, so
        # confirm the session with the page the coordinator actually needs.
        probe = self._request(session, USER_HOME_URL)
        probe_soup = to_soup(probe.text)
        if _looks_like_mfa(probe_soup):
            raise MyIrvingAuthError(
                "Multi-factor authentication is not supported by this integration"
            )
        if self._session_expired(probe, probe_soup):
            raise MyIrvingAuthError(
                "The Irving Energy portal rejected the email address or password"
            )

        self._logged_in = True

    def _ensure_session(self) -> requests.Session:
        """Create the requests session on first use and reuse it afterwards."""
        if self._session is None:
            session = requests.Session()
            session.headers.update(
                {
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-CA,en;q=0.9",
                }
            )
            self._session = session
            self._logged_in = False
        return self._session

    def _request(
        self,
        session: requests.Session,
        url: str,
        *,
        method: str = "get",
        **kwargs: Any,
    ) -> requests.Response:
        """Perform one request, converting transport failures to MyIrvingError."""
        kwargs.setdefault("timeout", self._timeout)
        kwargs.setdefault("allow_redirects", True)

        referer = kwargs.pop("referer", None)
        if referer is not None:
            kwargs.setdefault("headers", {})["Referer"] = referer

        try:
            response = session.request(method, url, **kwargs)
            response.raise_for_status()
        except requests.RequestException as err:
            # Only the URL is included: request bodies carry the password.
            raise MyIrvingError(f"Error communicating with {url}") from err
        return response

    @staticmethod
    def _session_expired(response: requests.Response, soup: BeautifulSoup) -> bool:
        """Detect a redirect back to the login page using the already parsed page."""
        return _is_login_url(response.url) or is_login_page(soup)


def _find_login_form(soup: BeautifulSoup) -> Any:
    """Return the login form element, falling back to the password form."""
    forms = soup.find_all("form")

    for form in forms:
        if form.find(attrs={"name": LOGIN_FIELD_SUBMIT}) is not None:
            return form
    for form in forms:
        if form.find("input", attrs={"type": "password"}) is not None:
            return form
    return None


def _hidden_values(form: Any) -> dict[str, str]:
    """Collect every hidden input so the portal receives its expected token fields."""
    values: dict[str, str] = {}
    for field in form.find_all("input"):
        name = field.get("name")
        if not name or (field.get("type") or "").lower() != "hidden":
            continue
        values[name] = field.get("value", "")
    return values


def _submit_value(form: Any) -> str:
    """Return the label of the login submit control, defaulting to Login."""
    for element in form.find_all(["input", "button"]):
        if element.get("name") != LOGIN_FIELD_SUBMIT:
            continue
        if value := element.get("value"):
            return value
        if (text := element.get_text(" ", strip=True)) != "":
            return text
    return "Login"


def _form_action(form: Any) -> str:
    """Resolve the login form action against the portal base URL."""
    action = form.get("action") or ""
    return urljoin(BASE_URL, action)


def _is_login_url(url: str) -> bool:
    """Return True when a response URL points at the portal login entry point."""
    path = urlparse(url).path.rstrip("/").lower()
    return path in _LOGIN_PATHS


def _looks_like_mfa(soup: BeautifulSoup) -> bool:
    """Return True when the parsed page advertises an unsupported MFA challenge."""
    text = soup.get_text(" ", strip=True).lower()
    return any(marker in text for marker in MFA_MARKERS)
