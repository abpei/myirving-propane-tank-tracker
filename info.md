# MyIrving Propane Tank Tracker

Home Assistant custom integration that reads live data from the Irving Energy
residential account portal (myaccount.irvingenergy.com).

## Features

- Propane tank fill percentage
- Last reading date
- Last delivery date and volume (litres)
- Today's price

## Notes

- This integration is unofficial and is not affiliated with, endorsed by, or
  supported by Irving Oil Limited. It works by logging into your own account
  portal with credentials you provide in the integration's config flow.
- Irving monitors report roughly once per day, so the default polling interval
  is conservative (6 hours).
- If your account uses multi factor authentication, this integration will not
  work; MFA is not supported.
