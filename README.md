# GT Banner Auto Register (Selenium)

Automates adding CRN(s) on Georgia Tech's Banner registration page.

**Login is manual (SSO/Duo).** Selenium only automates the add/submit flow after you're on the registration screen.

## Requirements
- Windows 10/11
- Python 3.10+
- Google Chrome

## Setup
```powershell
git clone <YOUR_REPO_URL>
cd <repo>
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
