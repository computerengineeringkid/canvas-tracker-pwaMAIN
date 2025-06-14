// static/script.js
document.addEventListener('DOMContentLoaded', function() {
    console.log("Canvas Tracker PWA script loaded.");

    // DOM Element References
    const coursesListDiv = document.getElementById('coursesList');
    const courseSelect = document.getElementById('courseSelect');
    const saveCourseSelectionButton = document.getElementById('saveCourseSelection');
    const upcomingAssignmentsListDiv = document.getElementById('upcomingAssignmentsList');
    const lateAssignmentsListDiv = document.getElementById('lateAssignmentsList');
    const gradedAssignmentsListDiv = document.getElementById('gradedAssignmentsList');
    const courseSelectionFeedbackDiv = document.getElementById('courseSelectionFeedback');
    const backendStatusEl = document.getElementById('backendStatus');
    const statusAreaEl = document.getElementById('statusArea');


    const SELECTED_COURSES_LS_KEY = 'canvasTrackerSelectedCourses';

    // --- Notification UI elements (PWA Push related - Will be commented out or removed) ---
    const enableNotificationsButton = document.getElementById('enableNotificationsButton'); // Assuming it exists in HTML
    const notificationStatusDiv = document.getElementById('notificationStatus'); // Assuming it exists
    const sendTestNotificationButton = document.getElementById('sendTestNotificationButton'); // Assuming it exists

    // Hide PWA notification buttons if they exist, as Discord is now primary
    if (enableNotificationsButton) enableNotificationsButton.style.display = 'none';
    if (notificationStatusDiv) notificationStatusDiv.style.display = 'none';
    if (sendTestNotificationButton) {
        // Re-purpose test notification button for Discord if desired, or hide.
        // For now, let's hide it as testing is via Discord directly.
        sendTestNotificationButton.style.display = 'none';
        // Or, if you want a button to trigger a test Discord message from frontend via backend:
        /*
        sendTestNotificationButton.textContent = 'Send Test Discord Alert';
        sendTestNotificationButton.style.display = 'inline-block'; // or 'block'
        sendTestNotificationButton.disabled = false;
        sendTestNotificationButton.addEventListener('click', async () => {
            if (notificationStatusDiv) {
                notificationStatusDiv.textContent = 'Sending test Discord notification...';
                notificationStatusDiv.className = 'mt-2 alert alert-info';
                notificationStatusDiv.style.display = 'block';
            }
            try {
                // The backend route /api/send_test_notification was modified to send a Discord test.
                // If you removed that backend route, this button won't work.
                // For this example, I'm assuming you might keep a test route.
                // const response = await fetch('/api/send_test_notification', { method: 'POST' });
                // const data = await response.json();
                // if (notificationStatusDiv) {
                //     if (response.ok) {
                //         notificationStatusDiv.textContent = `Test Discord notification attempt: ${data.message}`;
                //         notificationStatusDiv.className = 'mt-2 alert alert-success';
                //     } else {
                //         notificationStatusDiv.textContent = `Test Discord notification failed: ${data.error || 'Unknown error'}`;
                //         notificationStatusDiv.className = 'mt-2 alert alert-danger';
                //     }
                // }
                // For now, let's just log, assuming test route might be gone.
                console.log("Test Discord notification button clicked - functionality depends on backend '/api/send_test_notification'.");
                 if (notificationStatusDiv) {
                    notificationStatusDiv.textContent = 'Test Discord button clicked. Backend handles actual send.';
                    notificationStatusDiv.className = 'mt-2 alert alert-info';
                    notificationStatusDiv.style.display = 'block';
                 }

            } catch (error) {
                console.error('Error with test Discord notification button:', error);
                if (notificationStatusDiv) {
                    notificationStatusDiv.textContent = `Test Discord notification failed: ${error.message}`;
                    notificationStatusDiv.className = 'mt-2 alert alert-danger';
                }
            }
        });
        */
    }


    // --- Utility Functions ---
    function formatDueDate(dueDateString, includeTime = true) {
        if (!dueDateString) return 'No due date';
        try {
            const date = new Date(dueDateString);
            if (isNaN(date.getTime())) return 'Invalid date';
            const options = { year: 'numeric', month: 'short', day: 'numeric' };
            if (includeTime) { options.hour = '2-digit'; options.minute = '2-digit'; options.timeZoneName = 'short';}
            return date.toLocaleDateString(undefined, options);
        } catch (e) { console.warn("Could not parse date:", dueDateString, e); return dueDateString; }
    }
    function getSelectedCourseIds() { const saved = localStorage.getItem(SELECTED_COURSES_LS_KEY); return saved ? JSON.parse(saved) : []; }
    function saveSelectedCourseIds(selectedIds) { localStorage.setItem(SELECTED_COURSES_LS_KEY, JSON.stringify(selectedIds)); }
    function displayError(element, message) { if (element) { element.innerHTML = `<div class="alert alert-danger" role="alert">${message}</div>`; } else { console.error("displayError: null element", message); } }
    function displayInfo(element, message, isListGroupItem = true) {
         if (element) {
            if (isListGroupItem && element.classList.contains('list-group')) { element.innerHTML = `<p class="no-data list-group-item">${message}</p>`; }
            else if (element.classList.contains('row')) { element.innerHTML = `<div class="col-12"><p class="no-data">${message}</p></div>`; } // For coursesList
            else { element.innerHTML = `<p class="no-data">${message}</p>`; }
        } else { console.error("displayInfo: null element", message); }
    }

    // --- Course & Assignment Fetching/Display ---
    function fetchAndDisplayCourses() {
        if (!coursesListDiv || !courseSelect) { console.error("Course display elements not found."); return; }
        displayInfo(coursesListDiv, 'Loading courses...', false); // false for coursesList (row)
        courseSelect.innerHTML = ''; courseSelect.disabled = true; saveCourseSelectionButton.disabled = true;
        fetch('/api/courses')
            .then(response => { if (!response.ok) { return response.json().then(err => { throw new Error(err.message || `Failed to load courses: ${response.statusText} (Status ${response.status})`) }); } return response.json(); })
            .then(courses => {
                coursesListDiv.innerHTML = ''; const savedSelectedIds = getSelectedCourseIds().map(String);
                if (courses && courses.error) { displayError(coursesListDiv, `Error loading courses: ${courses.message}`); return; }
                if (courses && courses.length > 0) {
                    courses.forEach(course => {
                        const courseCard = `<div class="col-md-6 col-lg-4 mb-3"><div class="card course-card h-100"><div class="card-body"><h5 class="card-title">${course.name}</h5><p class="card-text text-muted">${course.course_code || 'No code'}</p><small class="text-muted">ID: ${course.id}</small></div></div></div>`;
                        coursesListDiv.insertAdjacentHTML('beforeend', courseCard);
                        const option = document.createElement('option'); option.value = course.id; option.textContent = `${course.name} (${course.course_code || 'N/A'})`;
                        if (savedSelectedIds.includes(String(course.id))) option.selected = true;
                        courseSelect.appendChild(option);
                    });
                    courseSelect.disabled = false; saveCourseSelectionButton.disabled = false;
                    fetchAndDisplayAllAssignments(); // Fetch assignments after courses are loaded
                } else { displayInfo(coursesListDiv, 'No active courses found. Check backend logs or Canvas.', false); }
            })
            .catch(error => { console.error('Error fetching courses:', error); displayError(coursesListDiv, `Failed to load courses: ${error.message}. Check API token, URL, and backend logs.`); });
    }

    function fetchAssignments(endpointPath, listDivElement, noDataMessage, processAssignmentFunction) {
        if (!listDivElement) { console.error(`Assignment display element for '${endpointPath}' not found.`); return; }
        displayInfo(listDivElement, `Loading ${endpointPath || 'upcoming'} assignments...`, true);
        let selectedIds = Array.from(courseSelect.selectedOptions).map(option => option.value);
        if (selectedIds.length === 0) selectedIds = getSelectedCourseIds(); // Use saved if nothing actively selected
        let queryParams = selectedIds.length > 0 ? '?course_ids=' + selectedIds.join(',') : '';
        const fullEndpoint = endpointPath ? `/api/assignments/${endpointPath}${queryParams}` : `/api/assignments${queryParams}`; // Default is upcoming

        fetch(fullEndpoint)
            .then(response => {
                if (!response.ok) {
                     return response.json().then(err => {
                        if (response.headers.get("content-type")?.includes("text/html")) throw new Error(`Server returned HTML error (Status ${response.status}). Check backend logs.`);
                        throw new Error(err.message || `API Error (Status ${response.status}): ${response.statusText}`)
                    }).catch(parseErr => { throw new Error(`Invalid server response (Status ${response.status}). ${parseErr.message}`); });
                } return response.json();
            })
            .then(assignments => {
                listDivElement.innerHTML = ''; // Clear previous
                if (assignments && assignments.error) { displayError(listDivElement, `Error loading assignments: ${assignments.message}`); return; }
                // Handle case where API returns a message like "No active courses selected..."
                if (assignments?.message && Array.isArray(assignments.data) && assignments.data.length === 0) {
                    displayInfo(listDivElement, assignments.message, true);
                    return;
                }
                if (assignments && assignments.length > 0) {
                    assignments.forEach(assignment => processAssignmentFunction(assignment, listDivElement));
                } else {
                    displayInfo(listDivElement, noDataMessage, true);
                }
            })
            .catch(error => { console.error(`Error fetching assignments '${fullEndpoint}':`, error); displayError(listDivElement, `Failed to load assignments: ${error.message}. Check backend logs.`); });
    }

    function processUpcomingAssignment(assignment, listDiv) {
        const item = `<a href="${assignment.html_url||'#'}" target="_blank" rel="noopener noreferrer" class="list-group-item list-group-item-action assignment-card"><div class="d-flex w-100 justify-content-between"><h5 class="mb-1 card-title">${assignment.name}</h5><small class="due-date">Due: ${formatDueDate(assignment.due_at)}</small></div><p class="mb-1 card-text">${assignment.course_name}</p><small class="points text-muted">Points: ${assignment.points_possible ?? 'N/A'}</small></a>`;
        listDiv.insertAdjacentHTML('beforeend', item);
    }
    function processLateAssignment(assignment, listDiv) {
        const item = `<a href="${assignment.html_url||'#'}" target="_blank" rel="noopener noreferrer" class="list-group-item list-group-item-action assignment-card late"><div class="d-flex w-100 justify-content-between"><h5 class="mb-1 card-title text-danger">${assignment.name}</h5><small class="due-date text-danger">Due: ${formatDueDate(assignment.due_at)} (${assignment.days_overdue}d overdue)</small></div><p class="mb-1 card-text">${assignment.course_name}</p><small class="points text-muted">Points: ${assignment.points_possible ?? 'N/A'}</small></a>`;
        listDiv.insertAdjacentHTML('beforeend', item);
    }
    function processGradedAssignment(assignment, listDiv) {
        let scoreDisplay = 'N/A'; if(assignment.score !== null) { scoreDisplay = `${assignment.score}`; if (assignment.points_possible > 0 && assignment.points_possible !== null) scoreDisplay += ` / ${assignment.points_possible}`; } if (assignment.grade) scoreDisplay += ` (${assignment.grade})`;
        const highlightClass = (assignment.newly_graded_alert || assignment.grade_changed_alert) ? 'grade-changed-highlight' : '';
        let alertText = ''; if (assignment.newly_graded_alert) alertText = '<br><small class="text-info"><em>Newly Graded!</em></small>'; else if (assignment.grade_changed_alert) alertText = '<br><small class="text-info"><em>Grade Updated!</em></small>';
        const item = `<a href="${assignment.html_url||'#'}" target="_blank" rel="noopener noreferrer" class="list-group-item list-group-item-action assignment-card graded ${highlightClass}"><div class="d-flex w-100 justify-content-between"><h5 class="mb-1 card-title">${assignment.name}</h5><small class="text-success graded-date">Score: ${scoreDisplay}</small></div><p class="mb-1 card-text">${assignment.course_name}</p><small class="text-muted">Graded: ${formatDueDate(assignment.graded_at, true)}</small>${alertText}</a>`;
        listDiv.insertAdjacentHTML('beforeend', item);
    }

    function fetchAndDisplayAllAssignments() {
        fetchAssignments('', upcomingAssignmentsListDiv, 'No upcoming assignments found.', processUpcomingAssignment); // Empty path for /api/assignments (upcoming)
        fetchAssignments('late', lateAssignmentsListDiv, 'No late assignments found.', processLateAssignment);
        fetchAssignments('graded', gradedAssignmentsListDiv, 'No recently graded assignments found.', processGradedAssignment);
    }

    if (saveCourseSelectionButton) {
        saveCourseSelectionButton.addEventListener('click', () => {
            const selectedIds = Array.from(courseSelect.selectedOptions).map(option => option.value);
            saveSelectedCourseIds(selectedIds);
            fetchAndDisplayAllAssignments(); // Refresh assignment lists based on new selection
            if (courseSelectionFeedbackDiv) {
                courseSelectionFeedbackDiv.textContent = 'Course selection saved and assignments updated!';
                courseSelectionFeedbackDiv.className = 'alert alert-success mt-2';
                setTimeout(() => {
                    courseSelectionFeedbackDiv.textContent = '';
                    courseSelectionFeedbackDiv.className = 'mt-2'; // Clear class or set to a default
                }, 3000);
            }
        });
    }

    // --- PWA Service Worker and Install Prompt Logic ---
    let deferredPrompt;
    const installPwaButton = document.getElementById('installPwaButton');
    if ('serviceWorker' in navigator) {
        // Register service worker from the root
        navigator.serviceWorker.register("/service-worker.js") // Ensure this path is correct
        .then(reg => console.log('Service Worker registered scope:', reg.scope))
        .catch(err => console.error('Service Worker registration failed:', err));
    }
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault(); deferredPrompt = e;
        if (installPwaButton) {
            installPwaButton.style.display = 'block'; // Show the install button
            installPwaButton.addEventListener('click', () => {
                installPwaButton.style.display = 'none'; // Hide after click
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then((choice) => {
                    console.log(choice.outcome === 'accepted' ? 'User accepted PWA install' : 'User dismissed PWA install');
                    deferredPrompt = null;
                });
            });
        }
    });
    window.addEventListener('appinstalled', () => { console.log('PWA installed'); if (installPwaButton) installPwaButton.style.display = 'none'; deferredPrompt = null; });


    // --- Notification Subscription Logic (PWA Push - Commented out as Discord is primary) ---
    /*
    function urlBase64ToUint8Array(base64String) {
        // ... (implementation was here)
    }

    async function subscribeUserToPush() {
        // ... (implementation was here)
    }

    async function sendSubscriptionToBackend(subscription) {
        // ... (implementation was here)
    }

    function updateNotificationButtonUI(isSubscribed, permissionBlocked = false) {
        // ... (implementation was here)
    }

    function updateNotificationStatus(message, alertType = 'alert-info', disableEnableButtonOnError = false) {
        // ... (implementation was here)
    }

    function initializeNotificationButton() {
        // ... (implementation was here)
    }
    */

    // Initial data load
    // Fetch backend status first
    if (statusAreaEl && backendStatusEl) {
        statusAreaEl.style.display = 'block'; // Show the status area
        fetch('/api/status')
            .then(response => {
                if (!response.ok) {
                    return response.json().then(errData => {
                       throw new Error(errData.message || `Network response was not ok (${response.status})`);
                    }).catch(() => { // Fallback if .json() fails
                       throw new Error(`Network response was not ok (${response.status}). Is the server running and configured?`);
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    backendStatusEl.textContent = data.status || 'Error from backend.';
                    statusAreaEl.classList.remove('alert-info', 'alert-success');
                    statusAreaEl.classList.add('alert-danger');
                    console.error("Backend status check indicated an error:", data.details || data.status);
                } else {
                    backendStatusEl.textContent = data.status || 'OK';
                    statusAreaEl.classList.remove('alert-info', 'alert-danger');
                    statusAreaEl.classList.add('alert-success');
                    // If backend is OK, then load courses
                    fetchAndDisplayCourses();
                }
            })
            .catch(error => {
                console.error('Error fetching backend status:', error);
                backendStatusEl.textContent = `Connection Failed: ${error.message}`;
                statusAreaEl.classList.remove('alert-info', 'alert-success');
                statusAreaEl.classList.add('alert-danger');
                // Display an error in the courses list as well
                if (coursesListDiv) displayError(coursesListDiv, "Could not connect to the backend. Please ensure the server is running and configured correctly, then refresh the page.");
            });
    } else {
         console.error("Status display elements not found in HTML. Cannot check backend status or load data.");
         // Fallback to trying to load courses anyway, but it will likely fail if status check elements are missing.
         fetchAndDisplayCourses();
    }

    // initializeNotificationButton(); // PWA Push related - commented out
});
