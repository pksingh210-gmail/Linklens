# ---------------- app.py ----------------
import auth.json_module_flask as db
import threading
import logging
import queue
import pandas as pd
import io
import webbrowser
import os
import re
import atexit
import signal
import sys
import traceback

from flask import Flask, render_template, request, redirect, url_for, session, Response, flash, send_file, jsonify, copy_current_request_context
from pathlib import Path
from datetime import datetime
from backend.linkedin_login import LinkedInLogin
from backend.linkedin_search import LinkedInSearch
from backend.linkedin_html import LinkedInHTML
from backend.linkedin_data_extract import parse_all_html
from backend.linkedin_contact_info import get_contact_info_for_profile

app = Flask(__name__)
app.secret_key = "supersecretkey"

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) 

# Fix URL building in background threads
# app.config["SERVER_NAME"] = "127.0.0.1:5000"
# app.config["PREFERRED_URL_SCHEME"] = "http"

# ---------------- LinkedIn Scraper Globals ----------------
status_queue = queue.Queue()
linkedin_results = []
scraper_lock = threading.Lock()
scraper_active = False
current_linkedin_user = None

# ---------------- Directories ----------------
DATA_DIR = Path("data")
LINKS_DIR = DATA_DIR / "links"
TEMP_DIR = DATA_DIR / "temp"
RESULTS_DIR = DATA_DIR / "results"

def ensure_data_folders():
    """
    Ensure required data folders exist.
    Safe to call multiple times.
    """
    for folder in [
        DATA_DIR,
        LINKS_DIR,
        TEMP_DIR,
        RESULTS_DIR,
    ]:
        folder.mkdir(parents=True, exist_ok=True)

def push_status(message):
    """Push scraper status updates to the queue."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status_queue.put(f"[{timestamp}] {message}")

def timestamped_filename(base_name, ext=None, folder=None):
    """
    Generate a timestamped filename.
    Example:
      timestamped_filename("results.xlsx")
      timestamped_filename("profile", ext="html")
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if ext:
        filename = f"{base_name}_{ts}.{ext.lstrip('.')}"
    else:
        if "." in base_name:
            name, extension = base_name.rsplit(".", 1)
            filename = f"{name}_{ts}.{extension}"
        else:
            filename = f"{base_name}_{ts}"

    if folder:
        return str(Path(folder) / filename)

    return filename

def clear_data_folders():
    """
    Deletes all files inside data folders,
    keeps folder structure intact.
    """
    folders = [
        RESULTS_DIR,
        LINKS_DIR,
        TEMP_DIR,
    ]

    for folder in folders:
        if folder.exists():
            for item in folder.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        import shutil
                        shutil.rmtree(item)
                except Exception as e:
                    print(f"Failed to delete {item}: {e}")

    # Recreate folders in case any were removed
    ensure_data_folders()

def enrich_df_with_contact_info(df, linkedin_cookies, status_cb=None, max_retries=2):
    """
    Enrich DataFrame with Email and Phone columns using LinkedIn contact overlay.
    Safe to re-run. Does not drop or modify any existing columns.
    
    Args:
        df (pd.DataFrame): DataFrame with profile data
        linkedin_cookies (dict): Authenticated LinkedIn cookies
        status_cb (callable): Optional callback for status updates
        max_retries (int): Number of retry attempts per profile
        
    Returns:
        pd.DataFrame: DataFrame with added 'Email' and 'Phone' columns
    """
    #if status_cb:
        #status_cb("📇 Starting contact info enrichment...")
    
    # Debug: Check cookies
    if not linkedin_cookies:
        #if status_cb:
            #status_cb("⚠️ WARNING: No cookies provided! Contact enrichment will be skipped.")
        df["Email"] = ""
        df["Phone"] = ""
        return df
    
    #if not linkedin_cookies.get("li_at"):
        #if status_cb:
            #status_cb("⚠️ WARNING: Missing li_at cookie! Contact enrichment will fail.")
    #else:
        #if status_cb:
            #status_cb(f"✅ Cookies available: {len(linkedin_cookies)} cookies, li_at present")

    emails_col = []
    phones_col = []
    
    total_profiles = len(df)
    success_count = 0
    skip_count = 0
    error_count = 0

    for idx, row in df.iterrows():
        # DEBUG: Print all column names on first iteration
        #if idx == 0 and status_cb:
            #status_cb(f"🔍 DEBUG: DataFrame columns: {list(df.columns)}")
        
        # Try multiple possible column names for profile URL
        profile_url = (
            row.get("ProfileLink")
            or row.get("profile_url")
            or row.get("Profile URL")
            or row.get("LinkedIn URL")
            or row.get("Profile Link")
            or ""
        )
        
        # DEBUG: Show what we found
        #if idx == 0 and status_cb:
            #status_cb(f"🔍 DEBUG: First profile URL: {profile_url}")

        # Default empty values (preserve row alignment)
        email_val = ""
        phone_val = ""

        # Extract vanity ID from profile URL
        vanity_id = ""
        if profile_url:
            # Handle various LinkedIn URL formats
            match = re.search(r'linkedin\.com/in/([^/\?]+)', profile_url)
            if match:
                vanity_id = match.group(1)
                #if idx == 0 and status_cb:
                    #status_cb(f"🔍 DEBUG: Extracted vanity ID: {vanity_id}")
            #else:
                #if status_cb:
                    #status_cb(f"⚠️ Could not extract vanity ID from: {profile_url}")

        # Skip if already enriched (important for re-runs)
        if row.get("Email") or row.get("Phone"):
            emails_col.append(row.get("Email", ""))
            phones_col.append(row.get("Phone", ""))
            skip_count += 1
            continue

        # Attempt to extract contact info if we have credentials and vanity ID
        if linkedin_cookies and vanity_id:
            for attempt in range(1, max_retries + 1):
                try:
                    #if status_cb and attempt == 1:
                        #status_cb(f"🔍 Fetching contact for {vanity_id} ({idx + 1}/{total_profiles})...")
                    
                    contact = get_contact_info_for_profile(vanity_id, linkedin_cookies)
                    
                    # Join multiple emails/phones with comma separator
                    email_val = ", ".join(contact.get("emails", []))
                    phone_val = ", ".join(contact.get("phones", []))

                    if email_val or phone_val:
                        success_count += 1
                        if status_cb:
                            items = []
                            if email_val:
                                items.append(f"📧 {email_val}")
                            if phone_val:
                                items.append(f"📞 {phone_val}")
                            #status_cb(f"✅ {vanity_id}: {', '.join(items)}")
                    #else:
                        #if status_cb:
                            #status_cb(f"ℹ️  No contact info found for {vanity_id}")

                    break  # Success, exit retry loop

                except Exception as e:
                    error_count += 1
                    error_msg = str(e)
                    
                    if attempt < max_retries:
                        #if status_cb:
                            #status_cb(f"⚠️ Retry {attempt}/{max_retries} for {vanity_id}")
                        import time
                        time.sleep(2)  # Wait before retry
                    #else:
                        # Final attempt failed
                        #if status_cb:
                            #status_cb(f"❌ Failed {vanity_id}: {error_msg[:80]}")

        emails_col.append(email_val)
        phones_col.append(phone_val)

    # Add or update columns
    df["Email"] = emails_col
    df["Phone"] = phones_col

    #if status_cb:
        #status_cb(f"📇 Enrichment complete: ✅ {success_count} | ⏭️ {skip_count} | ❌ {error_count} of {total_profiles}")

    return df

# ---------------- Background Scraper ----------------
def background_linkedin_scraper(params):
    global linkedin_results, scraper_active

    with scraper_lock:
        if scraper_active:
            push_status("⚠️ Scraper already running; ignoring duplicate request.")
            return
        scraper_active = True

    linkedin_results = []
    push_status("🔍 Starting LinkedIn Scraper...")
    
    login_scraper = None
    linkedin_cookies = {}  # Initialize here
    
    try:
        username = params.get("username")
        password = params.get("password")
        mode = params.get("mode", "full")
        headless = params.get("headless", True)
        excel_path = params.get("excel_path")
        job_title = params.get("job_title", "")
        country = params.get("country", "")
        city = params.get("city", "")

        if not username or not password:
            push_status("❌ Missing LinkedIn username or password")
            with scraper_lock:
                scraper_active = False
            return

        # ------------------ LOGIN ------------------
        login_scraper = LinkedInLogin(headless=headless, status_callback=push_status)
        login_scraper.login(username, password)
        
        if not login_scraper.logged_in:
            push_status("❌ Login failed. Cannot proceed.")
            with scraper_lock:
                scraper_active = False
            return

        # Extract cookies for contact enrichment
        linkedin_cookies = login_scraper.cookies
        push_status(f"✅ Login successful")

        # ------------------ COLLECT LINKS ------------------
        ensure_data_folders()

        links = []

        # Use uploaded Excel if provided and mode is HTML Only or HTML+Data
        if excel_path and mode in ["html_only", "html_and_data"]:
            try:
                df_links = pd.read_excel(excel_path)
                if "ProfileLink" in df_links.columns:
                    links = df_links["ProfileLink"].dropna().tolist()
                    # push_status(f"📥 Loaded {len(links)} links from uploaded Excel")
                #else:
                    # push_status("⚠️ Excel file must have a column named 'ProfileLink'")
            except Exception as e:
                push_status(f"❌ Failed to read Excel file: {e}")
                with scraper_lock:
                    scraper_active = False

        # Fallback: collect links via LinkedIn search if empty
        if not links and mode in ["full", "html_only", "html_and_data"]:
            search_scraper = LinkedInSearch(login_scraper.page, status_callback=push_status)
            links = search_scraper.collect_profile_links(
                job_title=job_title,
                country=country,
                max_results=int(params.get("max_results", 50)),
                city=city
            )
            
            # Save collected links to Excel file
            if links:
                links_filename = timestamped_filename(f"links_{job_title}_{city}_{country}", ".xlsx")
                links_path = LINKS_DIR / links_filename
                df_links = pd.DataFrame({"ProfileLink": links})
                df_links.to_excel(links_path, index=False)
                # push_status(f"💾 Saved {len(links)} links to: {links_path}")

        # ------------------ HTML ONLY ------------------
        if mode == "html_only":
            if links:
                html_scraper = LinkedInHTML(login_scraper.page, status_callback=push_status)
                html_count = 0
                for i, link in enumerate(links):
                    html_path = html_scraper.save_profile_html(link, TEMP_DIR)
                    if html_path:
                        html_count += 1
                    else:
                        push_status(f"❌ Failed to save profile HTML ({i+1}/{len(links)})")
                #push_status(f"💾 {html_count} Saved HTML Profile Files at {TEMP_DIR}")
            else:
                push_status("⚠️ No links to process for HTML collection")

        # ------------------ DATA ONLY ------------------
        elif mode == "data_only":
            push_status("📄 Parsing existing HTML for data extraction...")
            df = parse_all_html(role=job_title, loc=city or country)
            
            # CRITICAL: Enrich with email & phone BEFORE saving
            #push_status(f"📇 Starting contact enrichment for {len(df)} profiles...")
            df = enrich_df_with_contact_info(df, linkedin_cookies=linkedin_cookies, status_cb=push_status)

            linkedin_results.extend(df.to_dict(orient="records"))
            results_filename = timestamped_filename(f"linkedin_results_{job_title}_{city}_{country}", ".xlsx")
            results_path = RESULTS_DIR / results_filename
            df.to_excel(results_path, index=False)
            push_status(f"💾 Data extraction complete. Results saved: {results_path}")
            #push_status(f"DATA_FILE:{results_path}")
            with app.app_context():
                push_status(f"DOWNLOAD:{url_for('download_file', folder='results', filename=results_filename)}")
            push_status("RESULTS_READY")

        # ------------------ HTML + DATA ------------------
        elif mode == "html_and_data":
            if links:
                html_scraper = LinkedInHTML(login_scraper.page, status_callback=push_status)
                html_count = 0
                for i, link in enumerate(links):
                    html_path = html_scraper.save_profile_html(link, TEMP_DIR)
                    if html_path:
                        html_count += 1
                    else:
                        push_status(f"❌ Failed to save profile HTML ({i+1}/{len(links)})")
                push_status(f"💾 {html_count} Saved HTML Profile Files at {TEMP_DIR}")
            else:
                push_status("⚠️ No links to process for HTML collection")

            # After saving HTML, parse for data
            push_status("📄 Parsing HTML for data extraction...")
            df = parse_all_html(role=job_title, loc=city or country)
            
            # CRITICAL: Enrich with email & phone BEFORE saving
            # push_status(f"📇 Starting contact enrichment for {len(df)} profiles...")
            df = enrich_df_with_contact_info(df, linkedin_cookies=linkedin_cookies, status_cb=push_status)

            linkedin_results.extend(df.to_dict(orient="records"))
            results_filename = timestamped_filename(f"linkedin_results_{job_title}_{city}_{country}", ".xlsx")
            results_path = RESULTS_DIR / results_filename
            df.to_excel(results_path, index=False)
            #push_status(f"💾 Data extraction complete. Results saved: {results_path}")
            #push_status(f"DATA_FILE:{results_path}")
            with app.app_context():
                push_status(f"DOWNLOAD:{url_for('download_file', folder='results', filename=results_filename)}")
            push_status("RESULTS_READY")

        # ------------------ FULL MODE (default) ------------------
        else:  # mode == "full"
            if links:
                html_scraper = LinkedInHTML(login_scraper.page, status_callback=push_status)
                html_count = 0
                for i, link in enumerate(links):
                    html_path = html_scraper.save_profile_html(link, TEMP_DIR)
                    if html_path:
                        html_count += 1
                    #else:
                        # push_status(f"❌ Failed to save profile HTML ({i+1}/{len(links)})")
                # push_status(f"💾 {html_count} Saved HTML Profile Files at {TEMP_DIR}")
            # else:
                # push_status("⚠️ No links to process")

            # After saving HTML, parse for data
            push_status("📄 Parsing for data extraction...")
            df = parse_all_html(role=job_title, loc=city or country)
            
            # CRITICAL: Enrich with email & phone BEFORE saving
            # push_status(f"📇 Starting contact enrichment for {len(df)} profiles...")
            df = enrich_df_with_contact_info(df, linkedin_cookies=linkedin_cookies, status_cb=push_status)

            linkedin_results.extend(df.to_dict(orient="records"))
            results_filename = timestamped_filename(f"linkedin_results_{job_title}_{city}_{country}", ".xlsx")
            results_path = RESULTS_DIR / results_filename
            df.to_excel(results_path, index=False)
            #push_status(f"💾 Data extraction complete. Results saved: {results_path}")
            #push_status(f"DATA_FILE:{results_path}")
            #with app.app_context():
                #push_status(f"DOWNLOAD:{url_for('download_file', folder='results', filename=results_filename)}")
            push_status("RESULTS_READY")

        push_status("✅ Scraping completed successfully!")

    except Exception as e:
        push_status(f"❌ Error: {e}")
        push_status(f"❌ Traceback: {traceback.format_exc()}")
        with scraper_lock:
            scraper_active = False
    finally:
        if login_scraper:
            login_scraper.close()
        with scraper_lock:
            scraper_active = False

# ------------------- ROUTES -------------------
@app.route("/", methods=["GET","POST"])
@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = db.get_user(email)
        if user and db.verify_password(password, user["password_hash"]):
            session["logged_in"] = True
            session["user"] = user
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid email or password"
    return render_template("app.html", screen="login", title="Login", error=error, user=session.get("user"))

@app.route("/signup", methods=["GET","POST"])
def signup():
    error = None
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        address = request.form.get("address")
        try:
            db.add_user(name, email, password, address)
            return redirect(url_for("login"))
        except Exception as e:
            error = str(e)
    return render_template("app.html", screen="signup", title="Sign Up", error=error, user=session.get("user"))

@app.route("/logout")
def logout():
    clear_data_folders()
    session.clear()
    return redirect(url_for("login"))

@app.route("/reset_app", methods=["POST"])
def reset_app():
    if not session.get("logged_in"):
        return jsonify({"success": False, "message": "Not logged in"}), 401

    clear_data_folders()

    # Optional: clear in-memory results & queues
    global linkedin_results
    linkedin_results.clear()

    while not status_queue.empty():
        status_queue.get()

    return jsonify({"success": True, "message": "Application reset successfully"})

@app.route("/reset_request", methods=["GET","POST"])
def reset_request():
    message = None
    if request.method == "POST":
        email = request.form.get("email")
        try:
            token = db.set_reset_token(email)
            db.send_reset_email(email, token)
            message = "Reset link sent! Check your email."
        except Exception as e:
            message = str(e)
    return render_template("app.html", screen="reset_request", title="Reset Password", message=message, user=session.get("user"))

@app.route("/reset_password/<token>", methods=["GET","POST"])
def reset_password(token):
    error = None
    user = db.get_user_by_token(token)
    if not user:
        return "Invalid or expired token", 400
    if request.method == "POST":
        new_pass = request.form.get("new_password")
        try:
            db.update_password(user["email"], new_pass)
            return redirect(url_for("login"))
        except Exception as e:
            error = str(e)
    return render_template("app.html", screen="reset_password", title="Set New Password", error=error, user=session.get("user"))

@app.route("/dashboard", methods=["GET","POST"])
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    user = session.get("user")
    users_list = []

    last_inputs = {
        "linkedin_user": "",
        "linkedin_pass": "",
        "job_title": "",
        "country": "",
        "city": "",
        "max_results": 50,
        "headless": True,
        "scraper_mode": "full"
    }

    if request.method == "POST":
        linkedin_user = request.form.get("linkedin_user")
        linkedin_pass = request.form.get("linkedin_pass")
        job_title = request.form.get("job_title")
        country = request.form.get("country")
        city = request.form.get("city")
        max_results = request.form.get("max_results") or 50
        headless = "headless" in request.form
        scraper_mode = request.form.get("scraper_mode", "full")

        # Handle uploaded Excel file
        uploaded_file = request.files.get("input_excel")
        excel_path = None
        if uploaded_file and uploaded_file.filename:
            filename = uploaded_file.filename
            excel_path = LINKS_DIR / filename
            uploaded_file.save(excel_path)
            # push_status(f"📥 Uploaded Excel file: {excel_path}")

        last_inputs = {
            "linkedin_user": linkedin_user,
            "linkedin_pass": linkedin_pass,
            "job_title": job_title,
            "country": country,
            "city": city,
            "max_results": max_results,
            "headless": headless,
            "scraper_mode": scraper_mode
        }

        params = {
            "username": linkedin_user,
            "password": linkedin_pass,
            "job_title": job_title,
            "country": country,
            "city": city,
            "max_results": max_results,
            "headless": headless,
            "mode": scraper_mode,
            "excel_path": excel_path
        }
        threading.Thread(target=background_linkedin_scraper, args=(params,), daemon=True).start()
        flash("Scraper started — check the status panel.", "success")

    if user.get("is_admin"):
        users_list = db.get_all_users()

    return render_template(
        "app.html",
        screen="dashboard",
        title="Dashboard",
        results=linkedin_results,
        users_list=users_list,
        user=user,
        last_inputs=last_inputs
    )

@app.route("/linkedin_status")
def linkedin_status():
    def event_stream():
        while True:
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/get_results")
def get_results():
    return jsonify({"results": linkedin_results})

@app.route("/download_file/<folder>/<filename>")
def download_file(folder, filename):
    allowed = {"links": LINKS_DIR, "temp": TEMP_DIR, "results": RESULTS_DIR}
    if folder not in allowed:
        return "Invalid folder", 400
    file_path = allowed[folder] / os.path.basename(filename)
    if not file_path.exists():
        return "File not found", 404
    return send_file(file_path, as_attachment=True)

@app.route("/linkedin_download")
def linkedin_download():
    if not linkedin_results:
        return "No data yet.", 400
    df = pd.DataFrame(linkedin_results)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="linkedin_profiles.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
def cleanup_on_exit():
    print("🧹 Cleaning up data folders before exit...")
    clear_data_folders()

atexit.register(cleanup_on_exit)

def handle_signal(sig, frame):
    cleanup_on_exit()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)   # Ctrl+C
signal.signal(signal.SIGTERM, handle_signal)  # Kill process

# ------------------- RUN APP -------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)


