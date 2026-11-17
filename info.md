# MyIrving Propane Tank Tracker

Home Assistant custom integration for the Irving Energy MyIrving residential
account portal ([myaccount.irvingenergy.com](https://myaccount.irvingenergy.com/)).
It signs in with your own account credentials and creates five sensors from the
propane data on your account page.

## Sensors

- **Tank level**: percentage of tank capacity at the last monitor reading.
- **Last reading**: date of the last tank monitor reading.
- **Last delivery date**: date of the most recent delivery.
- **Last delivery volume**: litres delivered on that delivery.
- **Today's price**: price in dollars per litre for the current day. The unit
  is shown as `$` to match the Home Assistant core fuel-price convention; the
  number is a rate per litre, not a total.

## Installation

1. In HACS, add `https://github.com/abpei/myirving-propane-tank-tracker` as a
   custom repository of category **Integration**, then install **MyIrving
   Propane Tank Tracker**.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration**, choose
   **MyIrving Propane Tank Tracker**, and enter your portal email address and
   password.

Home Assistant 2026.11.0 or newer is required.

## Good to know

- The polling interval is configurable from 1 to 24 hours and defaults to 6
  hours. Tank readings usually arrive once a day or two.
- The config entry is titled **MyIrving Propane Tank**. Credentials live only
  in the entry data, are never logged, and the email is not used as a label.
- An expired portal session is renewed automatically. If the portal password
  changes, Home Assistant asks for the new password through a reauthentication
  flow and reloads the entry.
- Multi factor authentication is not supported.
- Entity ids include the `myirving_propane_tank_` device prefix plus an area
  prefix that Home Assistant adds, so match on the device prefix rather than a
  full id.
- The integration is unofficial and not affiliated with Irving Oil Limited.
  It scrapes the portal page for your own account, so a portal redesign can
  break it until an update is released.

## Documentation

See the [README](https://github.com/abpei/myirving-propane-tank-tracker#readme)
for the full sensor reference, price unit details, troubleshooting, and the
development and testing guide.
