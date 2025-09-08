# app.py
from flask import Flask, render_template, jsonify, request, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os
import requests
from datetime import datetime, timezone, timedelta
import json
import logging  # Added for better logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# from pywebpush import webpush, WebPushException # Commented out - PWA Push replaced by Discord

app = Flask(__name__)

# Configuration
CANVAS_API_TOKEN = os.environ.get('CANVAS_API_TOKEN', '8020~v9LZTJTeRtBZnwLZvxmkWNhMK7hRt2E3AZkcLCwUVAe463mhZnhAHT3we8GPMhxe')  # Replace with your actual token
CANVAS_BASE_URL = os.environ.get('CANVAS_BASE_URL','https://synchronic.uat.edu/')  # Replace with your Canvas URL
# --- Discord Webhook Configuration ---
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', 'https://discord.com/api/webhooks/1375369736753512538/XqFWhaXdbwtIZ8oQG1aWUmyFHkBra4QYAhBmGuGoJEqLULAXYqsT9jTQ90vYFUC04zG6')


db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'canvas_tracker.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}?timeout=20'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

app.config['SERVER_NAME'] = os.environ.get('FLASK_SERVER_NAME', '127.0.0.1:5001')
app.config['APPLICATION_ROOT'] = os.environ.get('FLASK_APPLICATION_ROOT', '/')
app.config['PREFERRED_URL_SCHEME'] = os.environ.get('FLASK_PREFERRED_URL_SCHEME', 'http')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

NOTIFICATION_THRESHOLDS = {
    "1w": timedelta(weeks=1), "5d": timedelta(days=5), "3d": timedelta(days=3),
    "1d": timedelta(days=1), "10h": timedelta(hours=10), "1h": timedelta(hours=1)
}
NOTIFICATION_LEVEL_ORDER = ["1w", "5d", "3d", "1d", "10h", "1h"]


class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    course_code = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    assignments = db.relationship('Assignment', backref='course', lazy=True, cascade="all, delete-orphan")

    def __repr__(self): return f"<Course {self.id}: {self.name}>"


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    points_possible = db.Column(db.Float, nullable=True)
    html_url = db.Column(db.String(500))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    graded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    score = db.Column(db.Float, nullable=True)
    grade = db.Column(db.String(50), nullable=True)
    workflow_state = db.Column(db.String(50), nullable=True)
    last_upcoming_notification_level = db.Column(db.String(50), nullable=True)
    last_late_notification_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_grade_notification_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def _get_aware_due_at(self):
        """Ensures due_at is timezone-aware (UTC)."""
        if self.due_at and self.due_at.tzinfo is None:
            return self.due_at.replace(tzinfo=timezone.utc)
        return self.due_at

    def is_late(self):
        aware_due_at = self._get_aware_due_at()
        if aware_due_at and aware_due_at < datetime.now(timezone.utc):
            return not self.submitted_at or self.workflow_state in ['unsubmitted', 'pending_review']
        return False

    def days_overdue(self):
        aware_due_at = self._get_aware_due_at()
        if self.is_late() and aware_due_at:
            return (datetime.now(timezone.utc) - aware_due_at).days
        return 0

    def __repr__(self):
        return f"<Assignment {self.id}: {self.name} (Course: {self.course_id})>"


def canvas_api_request(endpoint, method='GET', params=None):
    if CANVAS_API_TOKEN == 'YOUR_ACTUAL_CANVAS_API_TOKEN_HERE' or CANVAS_BASE_URL == 'YOUR_CANVAS_INSTANCE_URL_HERE' or not CANVAS_API_TOKEN or not CANVAS_BASE_URL:
        error_msg = "CRITICAL ERROR: Canvas API Token or Base URL is not configured in app.py."
        logging.error(error_msg)
        return {"error": "ConfigurationError", "message": error_msg, "status_code": 503}
    headers = {"Authorization": f"Bearer {CANVAS_API_TOKEN}"}
    url = f"{CANVAS_BASE_URL.rstrip('/')}/api/v1{endpoint}"
    try:
        response = requests.request(method, url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        logging.error(
            f"HTTP error: {http_err} - Status: {response.status_code} - URL: {url} - Response: {response.text}")
        error_details = {"error": "HTTPError", "message": str(http_err), "status_code": response.status_code}
        try:
            error_details["details"] = response.json()
        except ValueError:
            error_details["details"] = response.text
        if response.status_code == 401: error_details["error"] = "Unauthorized"; error_details[
            "message"] = "Canvas API token invalid/expired or lacks permissions."
        return error_details
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Request error: {req_err} - URL: {url}")
        return {"error": "RequestException", "message": str(req_err), "status_code": 500}
    except ValueError as json_err:
        logging.error(
            f"JSON decode error: {json_err} - URL: {url} - Response: {response.text if 'response' in locals() else 'N/A'}")
        return {"error": "JSONDecodeError", "message": str(json_err),
                "details": response.text if 'response' in locals() else 'N/A', "status_code": 500}


def parse_iso_datetime(date_string):
    if not date_string: return None
    try:
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        logging.warning(f"Could not parse datetime: {date_string}"); return None


def send_discord_notification(title, description, color=0x007bff, fields=None, include_everyone=True):
    if DISCORD_WEBHOOK_URL == 'YOUR_DISCORD_WEBHOOK_URL_HERE' or not DISCORD_WEBHOOK_URL:
        logging.error("Discord Webhook URL is not configured. Cannot send notification.")
        return False
    webhook_data = {"content": "@everyone" if include_everyone else "", "embeds": [
        {"title": title, "description": description, "color": color,
         "timestamp": datetime.now(timezone.utc).isoformat()}]}
    if fields and isinstance(fields, list): webhook_data["embeds"][0]["fields"] = fields
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=webhook_data, timeout=10)
        response.raise_for_status()
        logging.info(f"Discord notification sent: {title}")
        return True
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"Discord HTTP error: {http_err} - Status: {response.status_code} - Response: {response.text}")
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Discord Request error: {req_err}")
    except Exception as e:
        logging.error(f"Unexpected error sending Discord notification: {e}")
    return False


def format_timedelta_to_natural_language(td):
    if not isinstance(td, timedelta) or td.total_seconds() < 0: return "now"
    days = td.days;
    hours, remainder = divmod(td.seconds, 3600);
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days > 0: parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0 and days == 0: parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if not parts: return "very soon"
    return ", ".join(parts)


@app.route('/')
def index(): return render_template('index.html')


@app.route('/service-worker.js')
def service_worker(): return send_from_directory(os.path.join(app.root_path, 'static'), 'service-worker.js',
                                                 mimetype='application/javascript')


@app.route('/manifest.json')
def manifest(): return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json',
                                           mimetype='application/json')


@app.route('/api/status')
def api_status():
    if CANVAS_API_TOKEN == 'YOUR_ACTUAL_CANVAS_API_TOKEN_HERE' or CANVAS_BASE_URL == 'YOUR_CANVAS_INSTANCE_URL_HERE':
        return jsonify({"status": "Flask backend running, BUT Canvas API is NOT configured!", "error": True,
                        "details": "Update CANVAS_API_TOKEN and CANVAS_BASE_URL in app.py."}), 503
    if DISCORD_WEBHOOK_URL == 'YOUR_DISCORD_WEBHOOK_URL_HERE' or not DISCORD_WEBHOOK_URL:
        return jsonify(
            {"status": "Flask backend running, Canvas API configured, BUT Discord Webhook is NOT configured!",
             "error": True, "details": "Update DISCORD_WEBHOOK_URL in app.py."}), 503
    user_profile = canvas_api_request('/users/self/profile')
    if isinstance(user_profile, dict) and user_profile.get("error"):
        status_code = user_profile.get("status_code", 502)
        if status_code == 401: return jsonify(
            {"status": "Flask backend running, Canvas API FAILED (Unauthorized - check token/URL).", "error": True,
             "details": user_profile.get("message")}), 401
        if status_code == 503: return jsonify(
            {"status": "Flask backend running, Canvas API NOT configured.", "error": True,
             "details": user_profile.get("message")}), 503  # Should be caught by placeholder check
        return jsonify(
            {"status": f"Flask backend running, Canvas API FAILED ({user_profile.get('error')}).", "error": True,
             "details": user_profile.get("message")}), status_code
    return jsonify(
        {"status": "Flask backend is running, Canvas API and Discord Webhook connections OK!", "error": False})


@app.route('/api/test_discord', methods=['GET', 'POST'])
def test_discord_route():
    logging.info("Attempting to send test Discord notification via /api/test_discord route...")
    title = "👋 Test Notification from Canvas Tracker"
    description = "This is a test message sent from the `/api/test_discord` route in your Flask app. If you see this, your Discord webhook is working!"
    fields = [
        {"name": "Status", "value": "Looking Good! 👍", "inline": True},
        {"name": "Timestamp", "value": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z'), "inline": True}
    ]
    success = send_discord_notification(title, description, color=0x5865F2, fields=fields)
    if success:
        return jsonify({"message": "Test Discord notification sent successfully!",
                        "details": {"title": title, "description": description}}), 200
    else:
        return jsonify(
            {"message": "Failed to send test Discord notification. Check logs for errors.", "error": True}), 500


@app.route('/api/courses', methods=['GET'])
def get_courses_and_store():
    courses_data = canvas_api_request(
        '/courses',
        params={
            'enrollment_state': 'active',
            'per_page': 50,
            'include[]': 'term',
            'enrollment_type': 'student',
            'state[]': 'available'
        }
    )
    if isinstance(courses_data, dict) and courses_data.get("error"): return jsonify(courses_data), courses_data.get(
        "status_code", 500)
    active_courses_from_api = []
    returned_course_ids = []
    if isinstance(courses_data, list):
        for course_data in courses_data:
            if not isinstance(course_data, dict):
                continue
            end_at_str = course_data.get('end_at')
            if end_at_str:
                end_at_date = parse_iso_datetime(end_at_str)
                if end_at_date and end_at_date < datetime.now(timezone.utc):
                    logging.info(
                        f"Skipping course '{course_data.get('name')}' as it ended on {end_at_str}.")
                    with db.session.no_autoflush():
                        db_course_to_deactivate = db.session.get(Course, course_data['id'])
                        if db_course_to_deactivate:
                            db_course_to_deactivate.is_active = False
                    continue
            with db.session.no_autoflush():
                db_course = db.session.get(Course, course_data['id'])
            if db_course is None:
                db_course = Course(id=course_data['id'])
                db.session.add(db_course)
            db_course.name = course_data.get('name', 'Unnamed Course')
            db_course.course_code = course_data.get('course_code')
            db_course.is_active = True
            returned_course_ids.append(db_course.id)
            active_courses_from_api.append(
                {
                    'id': db_course.id,
                    'name': db_course.name,
                    'course_code': db_course.course_code,
                }
            )
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Database error storing courses: {e}")
            return (
                jsonify(
                    {
                        "error": "DatabaseOperationError",
                        "message": "Could not save course data.",
                    }
                ),
                500,
            )

        # Deactivate courses not returned by Canvas
        try:
            if returned_course_ids:
                courses_to_deactivate = Course.query.filter(
                    Course.is_active.is_(True),
                    Course.id.notin_(returned_course_ids),
                ).all()
            else:
                courses_to_deactivate = Course.query.filter_by(is_active=True).all()
            for course in courses_to_deactivate:
                course.is_active = False
                course.assignments.clear()
            if courses_to_deactivate:
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Database error deactivating courses: {e}")
            return (
                jsonify(
                    {
                        "error": "DatabaseOperationError",
                        "message": "Could not deactivate missing courses.",
                    }
                ),
                500,
            )

    active_courses_from_api.sort(key=lambda c: c['name'].lower())
    return jsonify(active_courses_from_api)


def _get_target_courses_for_assignments(selected_course_ids_str):
    target_course_ids = []
    if selected_course_ids_str:
        try:
            target_course_ids = [int(cid.strip()) for cid in selected_course_ids_str.split(',') if cid.strip()]
        except ValueError:
            return None, jsonify({"error": "Invalid course_ids format."}), 400
    courses_to_query = []
    if target_course_ids:
        for course_id_val in target_course_ids:
            with db.session.no_autoflush:
                db_course = db.session.get(Course, course_id_val)
            if db_course and db_course.is_active: courses_to_query.append({'id': db_course.id, 'name': db_course.name})
    else:
        active_db_courses = Course.query.filter_by(is_active=True).all()
        for db_course in active_db_courses: courses_to_query.append({'id': db_course.id, 'name': db_course.name})
    if not courses_to_query and not target_course_ids:
        logging.info("No active courses in DB or selected. Attempting to refresh courses from Canvas API.")
        with app.app_context():  # Ensure app context for url_for and db operations
            response_tuple = get_courses_and_store()
            if isinstance(response_tuple, tuple) and hasattr(response_tuple[0], 'get_json'):
                if response_tuple[1] >= 400:
                    logging.error(f"Failed to refresh courses during assignment fetch: {response_tuple[0].get_json()}")
                else:
                    active_db_courses = Course.query.filter_by(is_active=True).all()
                    for db_course in active_db_courses: courses_to_query.append(
                        {'id': db_course.id, 'name': db_course.name})
            elif isinstance(response_tuple, list):  # If get_courses_and_store directly returns the list
                active_db_courses = Course.query.filter_by(is_active=True).all()
                for db_course in active_db_courses: courses_to_query.append(
                    {'id': db_course.id, 'name': db_course.name})
        if not courses_to_query: logging.warning("Still no active courses found after refresh attempt.")
    return courses_to_query, None, None


def _process_and_store_assignments_from_api(assignments_data_from_api, course_id, course_name_for_assignment):
    processed_assignments_for_frontend = []
    if not (assignments_data_from_api and isinstance(assignments_data_from_api,
                                                     list)): return processed_assignments_for_frontend
    # now_utc = datetime.now(timezone.utc) # Defined in calling function (scheduler job)
    for api_assign in assignments_data_from_api:
        if not isinstance(api_assign, dict): continue
        assign_id = api_assign.get('id')
        if not assign_id: continue
        assign_obj = None;
        old_score = None;
        old_grade = None;
        old_workflow_state = None
        is_new_assignment = True
        with db.session.no_autoflush:
            assign_obj = db.session.get(Assignment, assign_id)
        if assign_obj:
            is_new_assignment = False; old_score = assign_obj.score; old_grade = assign_obj.grade; old_workflow_state = assign_obj.workflow_state
        else:
            assign_obj = Assignment(id=assign_id, course_id=course_id); db.session.add(assign_obj)
        assign_obj.name = api_assign.get('name', 'Unnamed Assignment');
        assign_obj.due_at = parse_iso_datetime(api_assign.get('due_at'))
        assign_obj.points_possible = api_assign.get('points_possible');
        assign_obj.html_url = api_assign.get('html_url');
        assign_obj.course_id = course_id
        submission_data = api_assign.get('submission');
        newly_graded_this_sync = False;
        grade_changed_this_sync = False
        if isinstance(submission_data, dict):
            new_submitted_at = parse_iso_datetime(submission_data.get('submitted_at'));
            new_graded_at = parse_iso_datetime(submission_data.get('graded_at'))
            new_score = submission_data.get('score');
            new_grade = submission_data.get('grade');
            new_workflow_state = submission_data.get('workflow_state')
            if new_workflow_state == 'graded':
                if old_workflow_state != 'graded':
                    newly_graded_this_sync = True
                elif new_score != old_score or new_grade != old_grade:
                    grade_changed_this_sync = True
            assign_obj.submitted_at = new_submitted_at;
            assign_obj.graded_at = new_graded_at;
            assign_obj.score = new_score;
            assign_obj.grade = new_grade;
            assign_obj.workflow_state = new_workflow_state
        elif api_assign.get('has_submitted_submissions') is False and not assign_obj.submitted_at:
            assign_obj.workflow_state = 'unsubmitted'
        elif not submission_data and not assign_obj.submitted_at:
            assign_obj.workflow_state = 'unsubmitted'
        if newly_graded_this_sync or grade_changed_this_sync:
            needs_notification = False
            if is_new_assignment and assign_obj.graded_at:
                needs_notification = True
            elif assign_obj.graded_at and (
                    assign_obj.last_grade_notification_sent_at is None or assign_obj.last_grade_notification_sent_at < assign_obj.graded_at):
                needs_notification = True
            if needs_notification:
                title = "✅ Assignment Graded!" if newly_graded_this_sync else "🔄 Grade Updated!"
                desc = f"Your assignment **{assign_obj.name}** in **{course_name_for_assignment}** has been graded."
                fields = [{"name": "Course", "value": course_name_for_assignment, "inline": True},
                          {"name": "Assignment", "value": f"[{assign_obj.name}]({assign_obj.html_url or '#'})",
                           "inline": True}, {"name": "Score",
                                             "value": f"{assign_obj.score if assign_obj.score is not None else 'N/A'} / {assign_obj.points_possible if assign_obj.points_possible is not None else 'N/A'}",
                                             "inline": True},
                          {"name": "Grade", "value": assign_obj.grade or "N/A", "inline": True}]
                if assign_obj.graded_at: fields.append(
                    {"name": "Graded At", "value": assign_obj.graded_at.strftime('%Y-%m-%d %I:%M %p %Z'),
                     "inline": False})
                send_discord_notification(title, desc, color=0x28a745, fields=fields)
                assign_obj.last_grade_notification_sent_at = assign_obj.graded_at
            else:
                logging.info(f"Graded notification for '{assign_obj.name}' skipped (already sent or older data).")
        processed_assignments_for_frontend.append(
            {'id': assign_obj.id, 'name': assign_obj.name, 'due_at': api_assign.get('due_at'),
             'points_possible': assign_obj.points_possible, 'html_url': assign_obj.html_url,
             'course_id': assign_obj.course_id, 'course_name': course_name_for_assignment,
             'submitted_at': submission_data.get('submitted_at') if submission_data else None,
             'graded_at': submission_data.get('graded_at') if submission_data else None,
             'workflow_state': assign_obj.workflow_state, 'score': assign_obj.score, 'grade': assign_obj.grade,
             'is_late': assign_obj.is_late(), 'days_overdue': assign_obj.days_overdue(),
             'newly_graded_alert': newly_graded_this_sync, 'grade_changed_alert': grade_changed_this_sync})
    return processed_assignments_for_frontend


@app.route('/api/assignments')
def get_upcoming_assignments_and_store():
    selected_course_ids_str = request.args.get('course_ids');
    courses_to_query_api, error_response, status_code = _get_target_courses_for_assignments(selected_course_ids_str)
    if error_response: return error_response, status_code
    if not courses_to_query_api: return jsonify(
        {"message": "No active courses selected or found for upcoming assignments.", "data": []}), 200
    all_upcoming_assignments_for_frontend = []
    for course_info in courses_to_query_api:
        course_id, course_name = course_info['id'], course_info['name']
        params = {'bucket': 'upcoming', 'per_page': 100, 'order_by': 'due_at', 'include[]': 'submission'}
        assignments_data = canvas_api_request(f'/courses/{course_id}/assignments', params=params)
        if isinstance(assignments_data, dict) and assignments_data.get("error"): logging.warning(
            f"Error fetching upcoming assignments for course {course_id} ({course_name}): {assignments_data.get('message')}"); continue
        processed = _process_and_store_assignments_from_api(assignments_data, course_id, course_name)
        for assign_data in processed:
            if assign_data['workflow_state'] not in ['submitted', 'graded', 'pending_review'] and assign_data[
                'due_at']: all_upcoming_assignments_for_frontend.append(assign_data)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback(); logging.error(f"DB Error committing upcoming assignments: {e}"); return jsonify(
            {"error": "DBError", "message": str(e)}), 500
    all_upcoming_assignments_for_frontend.sort(
        key=lambda x: parse_iso_datetime(x['due_at']) if x['due_at'] else datetime.max.replace(tzinfo=timezone.utc))
    return jsonify(all_upcoming_assignments_for_frontend)


@app.route('/api/assignments/late')
def get_late_assignments_and_store():
    selected_course_ids_str = request.args.get('course_ids');
    courses_to_query_api, error_response, status_code = _get_target_courses_for_assignments(selected_course_ids_str)
    if error_response: return error_response, status_code
    if not courses_to_query_api: return jsonify(
        {"message": "No active courses selected or found for late assignments.", "data": []}), 200
    all_late_assignments_for_frontend = []
    for course_info in courses_to_query_api:
        course_id, course_name = course_info['id'], course_info['name']
        params = {'per_page': 100, 'include[]': 'submission', 'order_by': 'due_at'}
        assignments_data = canvas_api_request(f'/courses/{course_id}/assignments', params=params)
        if isinstance(assignments_data, dict) and assignments_data.get("error"): logging.warning(
            f"Error fetching all assignments (for late check) for course {course_id} ({course_name}): {assignments_data.get('message')}"); continue
        processed = _process_and_store_assignments_from_api(assignments_data, course_id, course_name)
        for assign_data in processed:
            if assign_data['is_late']: all_late_assignments_for_frontend.append(assign_data)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback(); logging.error(f"DB Error committing late assignments: {e}"); return jsonify(
            {"error": "DBError", "message": str(e)}), 500
    all_late_assignments_for_frontend.sort(
        key=lambda x: parse_iso_datetime(x['due_at']) if x['due_at'] else datetime.min.replace(tzinfo=timezone.utc))
    return jsonify(all_late_assignments_for_frontend)


@app.route('/api/assignments/graded')
def get_graded_assignments_and_store():
    selected_course_ids_str = request.args.get('course_ids');
    courses_to_query_api, error_response, status_code = _get_target_courses_for_assignments(selected_course_ids_str)
    if error_response: return error_response, status_code
    if not courses_to_query_api: return jsonify(
        {"message": "No active courses selected or found for graded assignments.", "data": []}), 200
    all_graded_assignments_for_frontend = []
    for course_info in courses_to_query_api:
        course_id, course_name = course_info['id'], course_info['name']
        params = {'per_page': 100, 'order_by': 'due_at', 'include[]': 'submission'}
        assignments_data = canvas_api_request(f'/courses/{course_id}/assignments', params=params)
        if isinstance(assignments_data, dict) and assignments_data.get("error"): logging.warning(
            f"Error fetching all assignments (for graded check) for course {course_id} ({course_name}): {assignments_data.get('message')}"); continue
        processed = _process_and_store_assignments_from_api(assignments_data, course_id, course_name)
        for assign_data in processed:
            if assign_data['workflow_state'] == 'graded' and assign_data.get(
                'graded_at'): all_graded_assignments_for_frontend.append(assign_data)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback(); logging.error(f"DB Error committing graded assignments: {e}"); return jsonify(
            {"error": "DBError", "message": str(e)}), 500
    all_graded_assignments_for_frontend.sort(
        key=lambda x: parse_iso_datetime(x['graded_at']) if x.get('graded_at') else datetime.min.replace(
            tzinfo=timezone.utc), reverse=True)
    return jsonify(all_graded_assignments_for_frontend)


scheduler = BackgroundScheduler(daemon=True, timezone=str(timezone.utc))


def scheduled_assignment_sync_and_notifications_job():
    with app.app_context():
        now_utc = datetime.now(timezone.utc)
        logging.info(
            f"[{now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}] Running: Scheduled Assignment Sync & Notifications Job")
        logging.info("    Job: Refreshing courses from Canvas...")
        with app.test_client() as client:
            try:
                course_refresh_response = client.get(url_for('get_courses_and_store'))
                if course_refresh_response.status_code >= 400: logging.error(
                    f"    Job: Failed to refresh courses. Status: {course_refresh_response.status_code}. Response: {course_refresh_response.get_data(as_text=True)}")
            except Exception as e:
                logging.error(f"    Job: Error during course refresh API call: {e}")
        logging.info("    Job: Syncing all assignment data (upcoming, late, graded)...")
        active_courses = Course.query.filter_by(is_active=True).all();
        active_course_ids = [str(c.id) for c in active_courses]
        if not active_course_ids: logging.warning(
            "    Job: No active courses in DB. Full assignment sync might be limited.")
        course_ids_param = ",".join(active_course_ids) if active_course_ids else None
        with app.test_client() as client:
            try:
                logging.info("    Job: Fetching/processing upcoming assignments...")
                client.get(url_for('get_upcoming_assignments_and_store', course_ids=course_ids_param))
                logging.info("    Job: Fetching/processing late assignments...")
                client.get(url_for('get_late_assignments_and_store', course_ids=course_ids_param))
                logging.info("    Job: Fetching/processing graded assignments (also triggers graded notifications)...")
                client.get(url_for('get_graded_assignments_and_store', course_ids=course_ids_param))
            except Exception as e:
                logging.error(f"    Job: Error during assignment sync API calls: {e}")

        logging.info("    Job: Checking for upcoming assignment notifications...")
        upcoming_assignments_to_notify = Assignment.query.filter(
            Assignment.due_at.isnot(None),  # Ensure due_at is not null
            Assignment.workflow_state.notin_(['submitted', 'graded'])
        ).join(Course).filter(Course.is_active == True).all()  # Only for active courses

        for assign in upcoming_assignments_to_notify:
            aware_due_at = assign._get_aware_due_at()  # Use the helper method
            if not aware_due_at:
                logging.warning(
                    f"Assignment ID {assign.id} ('{assign.name}') has no valid/aware due_at date. Skipping upcoming notification check.")
                continue

            if aware_due_at <= now_utc:  # If it's already past due, it will be handled by overdue logic
                continue

            time_remaining = aware_due_at - now_utc
            current_level_sent_idx = NOTIFICATION_LEVEL_ORDER.index(
                assign.last_upcoming_notification_level) if assign.last_upcoming_notification_level in NOTIFICATION_LEVEL_ORDER else -1

            for idx, level_key in enumerate(NOTIFICATION_LEVEL_ORDER):
                threshold_time = NOTIFICATION_THRESHOLDS[level_key]
                if timedelta(0) < time_remaining <= threshold_time:
                    if idx > current_level_sent_idx:
                        course_name = assign.course.name if assign.course else "Unknown Course";
                        title = f"📢 Upcoming Assignment Reminder! ({level_key})"
                        desc = f"Assignment **{assign.name}** for **{course_name}** is due soon!";
                        due_date_str = aware_due_at.strftime('%A, %B %d, %Y at %I:%M %p %Z')
                        time_rem_str = format_timedelta_to_natural_language(time_remaining)
                        fields = [{"name": "Course", "value": course_name, "inline": True},
                                  {"name": "Assignment", "value": f"[{assign.name}]({assign.html_url or '#'})",
                                   "inline": True},
                                  {"name": "Due", "value": f"{due_date_str} (in {time_rem_str})", "inline": False}]
                        if send_discord_notification(title, desc, color=0xffc107,
                                                     fields=fields): assign.last_upcoming_notification_level = level_key; db.session.commit(); logging.info(
                            f"Sent upcoming '{level_key}' notification for '{assign.name}'.")
                        break

        logging.info("    Job: Checking for overdue assignment notifications...")
        overdue_assignments_to_notify = Assignment.query.filter(
            Assignment.due_at.isnot(None),  # Ensure due_at is not null
            Assignment.workflow_state.notin_(['submitted', 'graded'])
        ).join(Course).filter(Course.is_active == True).all()  # Only for active courses

        for assign in overdue_assignments_to_notify:
            aware_due_at = assign._get_aware_due_at()  # Use the helper method
            if not aware_due_at:
                logging.warning(
                    f"Assignment ID {assign.id} ('{assign.name}') has no valid/aware due_at date. Skipping overdue notification check.")
                continue

            if aware_due_at >= now_utc:  # If it's not actually overdue by now_utc, skip
                continue

            # Check if it's truly late (is_late() method already uses _get_aware_due_at())
            if not assign.is_late():
                continue

            if assign.last_late_notification_sent_at is None or assign.last_late_notification_sent_at.date() < now_utc.date():
                course_name = assign.course.name if assign.course else "Unknown Course"
                days_late = (now_utc - aware_due_at).days  # now_utc and aware_due_at are both aware
                title = "🚨 Overdue Assignment Alert!"
                desc = f"Assignment **{assign.name}** for **{course_name}** is overdue.";
                due_date_str = aware_due_at.strftime('%A, %B %d, %Y at %I:%M %p %Z')
                fields = [{"name": "Course", "value": course_name, "inline": True},
                          {"name": "Assignment", "value": f"[{assign.name}]({assign.html_url or '#'})", "inline": True},
                          {"name": "Originally Due", "value": due_date_str, "inline": False},
                          {"name": "Status", "value": f"{days_late} day{'s' if days_late != 1 else ''} overdue",
                           "inline": False}]
                if send_discord_notification(title, desc, color=0xdc3545,
                                             fields=fields): assign.last_late_notification_sent_at = now_utc; db.session.commit(); logging.info(
                    f"Sent overdue notification for '{assign.name}'.")

        logging.info(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}] Finished: Scheduled Job")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        logging.info("Running initial assignment sync and notification check on startup...")
        scheduled_assignment_sync_and_notifications_job()  # Run once immediately on startup
        logging.info("Initial startup sync and notification check complete.")

        if not scheduler.get_jobs():
            # Schedule the job to run every 30 minutes, starting 30 minutes from now to avoid overlap with initial run
            scheduler.add_job(
                scheduled_assignment_sync_and_notifications_job,
                trigger=IntervalTrigger(minutes=30, start_date=datetime.now(timezone.utc) + timedelta(minutes=30)),
                id='job_scheduled_assignment_sync_and_notifications',
                replace_existing=True,
                misfire_grace_time=600  # 10 minutes
            )
            logging.info("Scheduler: Added 'scheduled_assignment_sync_and_notifications_job' to run every 30 minutes.")
        else:
            logging.info(
                "Scheduler: Job 'scheduled_assignment_sync_and_notifications_job' already exists or was reconfigured.")

        try:
            if not scheduler.running:
                scheduler.start()
                logging.info("Scheduler started.")
        except Exception as e:
            logging.error(f"Error starting scheduler: {e}")

    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
