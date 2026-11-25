# WasteDeal

WasteDeal is a local waste-material listing and search app. Its backend now uses Python and SQLite; XAMPP, Apache, and MySQL are not required.

## Start on Windows

1. Install Python 3.10 or newer and make sure the Python launcher (`py`) or `python` is available.
2. Double-click `run.bat` in this folder. On first launch it creates a `.venv` environment and installs Flask.
3. Open http://127.0.0.1:5000 in your browser.
4. Keep the command window open while using the app. Press Ctrl+C to stop the server.

The app creates its SQLite database at `instance/wastedeal.sqlite3` the first time it starts. No separate database setup is needed. You can also start it from a terminal with `py -m venv .venv`, `.venv\Scripts\python -m pip install -r requirements.txt`, then `.venv\Scripts\python app.py`.

## Run from VS Code

1. Open this project folder in VS Code (the folder containing `app.py`).
2. Install the Microsoft Python extension if VS Code prompts you for it.
3. Open **Run and Debug** and choose **WasteDeal: Python + SQLite**.
4. Press **F5**. The included task creates `.venv`, installs Flask when needed, starts the app, and opens it in your browser.

Use the Python app launch configuration instead of the Live Server extension: Live Server only serves static files and does not run the Python backend or SQLite routes. Stop the app with **Shift+F5**.

## Backend features

- Account sign-up, sign-in, and sign-out, with passwords stored as secure hashes
- Waste listing creation and searchable listings
- Hazardous-waste disposal requests
- Contact and quote request storage
- Carbon-factor lookup for the existing calculator

Form submissions are saved locally in SQLite. This project does not send email or process online payments. Search results let buyers contact the listing owner by email.

## Sample data and analytics

The app adds 19 clearly marked fictional sample records on its first startup: 9 waste listings, 4 disposal requests, 3 contact messages, and 3 quote requests. Sample rows use reserved `.invalid` email addresses and are labeled in search results; they are examples, not real sellers.

Open **Analytics** in the site navigation or visit `/analytics` to see listing totals, material quantities, six-month listing activity, request counts, and leading listing locations. The dashboard reads the SQLite database and includes both sample and real records. Existing real data is preserved.

## Public demo deployment

The repository includes a Render Blueprint (`render.yaml`). Connect the public GitHub repository in Render and create the `wastedeal-demo` web service from that Blueprint. It uses Render's free web service, runs with Gunicorn, and enables read-only demo mode so visitors' form details and passwords are not stored. The sample SQLite database is recreated when the service starts; this deployment is for showcasing the site, not for preserving submitted data. Free services can sleep after inactivity and take about a minute to wake.

## Existing XAMPP data

The project did not include a MySQL export or a consistent schema to import. Existing XAMPP data must be exported and converted separately if you want to keep it. The Python app does not need the old PHP backend.

## Notes

The existing carbon calculator uses demonstration factors carried over from the old project; they are not validated environmental measurements. Some older informational pages reference an `assets/` directory that was not present in the supplied project folder, so those pages may not have their original styling and images.
