# IT Security Policy

## Password and Multi-Factor Authentication (MFA) Rules

All corporate accounts must comply with the following password policy:
- Minimum password length: **14 characters**.
- Passwords must contain at least one uppercase letter, one lowercase letter, one digit, and one special character.
- Passwords must be rotated every **90 days**; reuse of the last 12 passwords is prohibited.
- **Multi-Factor Authentication (MFA)** is mandatory for all corporate accounts, including email, VPN, HR portal, and cloud services.
- MFA must use an authenticator app (Google Authenticator, Microsoft Authenticator) or a hardware security key (YubiKey). SMS-based MFA is not permitted for sensitive systems.

## Laptop Refresh Cycle

Corporate laptops are eligible for replacement on a **36-month (3-year) cycle**.
- Refresh requests are submitted through the IT Service Portal (ticket category: *Hardware Refresh*).
- Laptops older than 36 months that are still functional may continue in service until a replacement is provisioned, but IT will not guarantee support for hardware defects.
- Early refresh (before 36 months) requires VP-level approval and is subject to budget availability.
- Upon refresh, the old device must be returned to IT within 5 business days for secure data wipe and disposal.

## VPN Requirements

- **WireGuard VPN** is required for all remote access to internal databases, file servers, and production systems.
- Employees must connect to the WireGuard VPN before accessing any internal resource not exposed via the public internet.
- VPN clients must be installed and configured by the IT team; self-managed VPN clients are not supported.
- Split tunneling is disabled; all traffic routes through the corporate gateway while VPN is active.

## Lost or Stolen Device Reporting

- Employees must report a lost or stolen corporate device to the IT Security team **within 2 hours** of discovering the loss.
- Reporting is done via the IT Security hotline (+1-800-555-SEC1) or the emergency IT ticket portal.
- Upon report, IT will immediately trigger remote wipe and revoke device credentials.
- Failure to report within the 2-hour window may result in disciplinary action as per the Employee Code of Conduct.
- A formal incident report must be completed and submitted to the IT Security team within 24 hours.
