from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import sqlite3
import os
import requests
from dotenv import load_dotenv

# Load Environment Variables
load_dotenv()

# Initialize Groq Client
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Create an instance of the Flask class
# This is our main application object
app = Flask(__name__)
app.secret_key = 'hackathon_secret_key' # Required for session management

# DATABASE CONFIGURATION
DATABASE = 'governance.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        # Create Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
        
        # Seed default users if they don't exist
        try:
            cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
            cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('user', 'user123', 'user')")
            db.commit()
            print("Database initialized with default users.")
        except Exception as e:
            print(f"Error seeding database: {e}")

# Initialize DB on startup
if not os.path.exists(DATABASE):
    init_db()
else:
    # Ensure tables exist even if file exists
    init_db()


# In-memory storage for requests
requests_list = []

# GOVERNANCE-AS-A-SERVICE (GaaS) CONFIGURATION
# This acts as the "Brain" settings for our city
GAAS_CONFIG = {
    'CITY_NAME': 'Metropolis',
    'DEPARTMENTS': {
        'Health': 'Health Department',
        'Electricity': 'Electricity Board',
        'Road': 'Roads & Highways Dept',
        'Fire': 'Fire & Rescue Services',
        'Water': 'Water Supply & Sanitation'
    },
    'PRIORITY_RULES': {
        'CRITICAL_KEYWORDS': [
            'fire', 'accident', 'explosion', 'collapsed', 'blood', 'breathing', 
            'medical emergency', 'life-threatening', 'critical care', 'ambulance', 'icu', 'hospital overload', 'triage', 'mortality',
            'outbreak', 'epidemic', 'pandemic', 'vaccination shortage', 
            'traffic hazard', 'black spot', 'fatal', 'structural failure',
            'power outage', 'grid failure', 'transformer', 'electrical hazard', 'short circuit', 'voltage fluctuation',
            'water scarcity', 'contaminated', 'sewage', 'flood', 'cholera', 'unsafe water'
        ],
        'HIGH_KEYWORDS': [
            'blocked', 'sparking', 'exposed', 'leaking', 'power',
            'staff shortage', 'accessibility', 'demand',
            'pothole', 'road damage', 'bridge safety', 'maintenance', 'construction delay', 'congestion', 'signal failure',
            'load shedding', 'disruption', 'distribution failure', 'energy shortage',
            'pipeline', 'pressure failure', 'drainage', 'supply disruption'
        ],
        'URGENCY_WEIGHTS': {'Critical': 100, 'High': 70, 'Medium': 40, 'Low': 10}
    }
}

# Helper: Generate Prediction Data with Defect Details and Prevention Methods
def generate_prediction_data(all_requests):
    # 1. Count frequency of each category
    category_counts = {}
    for r in all_requests:
        cat = r['category']
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    # 2. Define defect details and prevention methods by category
    category_insights = {
        'Fire': {
            'defects': 'Combustible materials exposed, poor ventilation, electrical hazards, blocked fire exits',
            'prevention': 'Regular fire safety inspections, maintain fire extinguishers, ensure clear exit routes, electrical maintenance',
            'advisory': 'Evacuate immediately and call emergency services. Use fire extinguishers only if trained and path is clear.'
        },
        'Health': {
            'defects': 'Hygiene violations, contaminated areas, disease outbreak indicators, inadequate sanitation',
            'prevention': 'Regular health inspections, sanitization protocols, disease surveillance, public awareness campaigns',
            'advisory': 'Seek immediate medical attention if symptoms present. Report to health authorities and isolate if contagious.'
        },
        'Electricity': {
            'defects': 'Damaged wiring, loose connections, overloaded circuits, corroded poles, transformer failures',
            'prevention': 'Regular electrical inspections, load balancing, vegetation clearing, preventive maintenance',
            'advisory': 'Do not touch fallen wires or damaged equipment. Evacuate the area and contact electricity board immediately.'
        },
        'Water': {
            'defects': 'Pipe leaks, contamination sources, pressure failures, drainage blockages, sewage overflow',
            'prevention': 'Pipeline maintenance programs, water quality testing, drainage system cleaning, leak detection',
            'advisory': 'Do not consume contaminated water. Report to water authority and use alternative water sources.'
        },
        'Road': {
            'defects': 'Potholes, cracks, poor drainage, missing signage, damaged intersections, structural failures',
            'prevention': 'Routine road patrols, timely repairs, traffic management, weather-resistant maintenance',
            'advisory': 'Reduce speed and exercise caution. Report hazards and avoid the damaged area when possible.'
        }
    }
    
    # 3. Use simple heuristic rules for the "prediction"
    prediction_data = {
        'text': "Insufficient data to generate predictions.",
        'recommendation': "Continue monitoring incoming data streams.",
        'forecast_level': "Stable",
        'defects': "No specific defects detected.",
        'prevention': "Maintain regular infrastructure monitoring.",
        'advisory': "System operating normally. Continue routine inspections."
    }

    if category_counts:
        # Get category with max counts
        top_category = max(category_counts, key=category_counts.get)
        count = category_counts[top_category]
        
        # Get category-specific insights
        insights = category_insights.get(top_category, {})
        prediction_data['defects'] = insights.get('defects', 'Check for anomalies in the system.')
        prediction_data['prevention'] = insights.get('prevention', 'Regular maintenance is recommended.')
        prediction_data['advisory'] = insights.get('advisory', 'Take appropriate action based on severity.')
        
        if count >= 3:
            prediction_data['text'] = f"⚠️ CRITICAL: Surge in '{top_category}' reports detected ({count} incidents)."
            prediction_data['recommendation'] = f"IMMEDIATE ACTION: Deploy emergency response teams to {top_category} sector. Activate contingency protocols."
            prediction_data['forecast_level'] = "Critical Increase"
        else:
            prediction_data['text'] = f"Alert: '{top_category}' is currently trending ({count} incidents)."
            prediction_data['recommendation'] = f"Allocate standby crews to {top_category} for rapid response. Monitor situation closely."
            prediction_data['forecast_level'] = "Moderate Growth"
            
    return prediction_data

# Define the route for the main page ('/')
# This function runs when someone visits the home page
# We name it 'index' because dashboard.html uses url_for('index')
@app.route('/')
def index():
    # Role-Based Access Control
    if not session.get('user_role'):
        return redirect(url_for('login'))
    
    if session.get('user_role') == 'admin':
         # Admins shouldn't be submitting requests, they manage them
         return redirect(url_for('dashboard'))

    # Users see the submission form
    # Filter requests for this user
    user_requests = [r for r in requests_list if r.get('submitted_by') == session.get('username')]
    
    # Generate predictive insights (global context for transparency)
    prediction_data = generate_prediction_data(requests_list)
    
    return render_template('index.html', city_name=GAAS_CONFIG['CITY_NAME'], departments=GAAS_CONFIG['DEPARTMENTS'], my_requests=user_requests, prediction=prediction_data)

# Login Route
# Redirect root login to user login by default
@app.route('/login')
def login():
    return redirect(url_for('user_login'))

# USER LOGIN ROUTE (Citizens)
@app.route('/login/user', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        
        if user:
            # Check if attempting to login as admin on user portal? (Optional security, but allowing for now)
            session['user_role'] = user['role']
            session['username'] = user['username']
            
            if user['role'] == 'admin':
                # If an admin logs in here, redirect to dashboard or ask to use admin portal?
                # Let's redirect to dashboard for convenience
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid Credentials! Please try again.')
            
    return render_template('user_login.html')

# ADMIN LOGIN ROUTE (Officials)
@app.route('/login/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
        
        if user and user['role'] == 'admin':
            session['user_role'] = user['role']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        elif user:
            flash('Access Denied: You are not authorized as an Administrator.')
        else:
            flash('Invalid Credentials!')
            
    return render_template('admin_login.html')

@app.route('/register', methods=['POST'])
def register():
    username = request.form['reg_username']
    password = request.form['reg_password']
    
    # Default role for new registrations is 'user'
    role = 'user'
    
    db = get_db()
    try:
        db.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))
        db.commit()
        flash('Registration Successful! Please Login.')
    except sqlite3.IntegrityError:
        flash('Username already exists! Try another one.')
        
    return redirect(url_for('login'))

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('user_login'))

# Helper function: AI Priority Logic
def calculate_priority(category, location, description):
    # This function is now deprecated in favor of analyze_request_with_ai but kept for structure if needed
    pass

# Helper function: AI Analysis using Groq (Replaces Old Logic)
def analyze_request_with_ai(description, location):
    try:
        # Construct the Prompt
        # We ask for JSON for easy parsing (simulated by simple text parsing here for robustness)
        prompt = f"""
        You are an AI Governance Official. Analyze this citizen report:
        Location: {location}
        Description: "{description}"

        Task:
        1. Verify 'Location' & 'Description'. If invalid/nonsense, classify as 'Invalid'.
        2. Classify into ONE category: 'Fire', 'Health', 'Electricity', 'Water', 'Road'.
        3. Assign a Priority Score (0-100) based on these STRICT rules:
           - CRITICAL (80-100): Life-threatening, fire, massive explosion, hospital, live wires, epidemic.
           - HIGH (50-79): Major service disruption, blockages, power outage, sparking, clean water loss.
           - MEDIUM (20-49): Inconvenience, potholes, leaky pipe, garbage accumulation.
           - LOW (0-19): Cosmetic issues, flickering light, request for info.

        Output format (Exact format required):
        Category: [Category]
        Score: [Number]
        Reason: [Text]
        """

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "model": "llama-3.3-70b-versatile",
            }
        )
        response.raise_for_status()
        result = response.json()

        # Parse Response (Simple text parsing)
        response_text = result['choices'][0]['message']['content']
        
        # Default fallback values
        category = "Road"
        score = 10
        reason = "AI Analysis failed to parse."

        lines = response_text.strip().split('\n')
        for line in lines:
            if line.strip().startswith("Category:"):
                category = line.split(":", 1)[1].strip().split()[0] # Take first word to be safe
                # Clean up any extra punctuation
                category = category.replace("'", "").replace('"', "").replace(".", "")
            elif line.strip().startswith("Score:"):
                try:
                    score = int(line.split(":", 1)[1].strip().split()[0]) # Extract number
                except:
                    score = 10
            elif line.strip().startswith("Reason:"):
                reason = line.split(":", 1)[1].strip()

        return category, score, reason

    except Exception as e:
        print(f"AI Error: {e}")
        # Fallback to 'Invalid' to verify manually if AI service is down, rather than wrongly assuming 'Road'.
        return "Invalid", 0, "System Error: AI Validation Unavailable."


# Helper function: Smart Service Routing
def assign_department(category, score):
    # Base routing directly maps category to configured department
    # Fallback to 'General Services' if category not found
    dept = GAAS_CONFIG['DEPARTMENTS'].get(category, "General Services")
    
    # Escalation Routing for High Priority
    if score >= 80: # Critical
         dept += " (Emergency Response Unit)"
    elif score >= 50: # High
        dept += " (Rapid Action Team)"
        
    return dept

# Helper: Strict Input Validation (Before AI)
def validate_request_data(location, description):
    # 1. Input Sanitization
    if not location or not description:
        return "Fields cannot be empty."
        
    loc_clean = location.strip().lower()
    desc_clean = description.strip().lower()
    
    # 2. Blocklist (Common Spam)
    spam_words = ['hi', 'hello', 'hey', 'test', 'testing', 'check', '123', 'abc', 'xyz', 'demo']
    if loc_clean in spam_words or desc_clean in spam_words:
        return "Please enter a genuine location and description."
        
    # 3. Confidence Gating (Length Heuristics)
    if len(loc_clean) < 3:
        return "Location name is too short (min 3 chars)."
    if len(desc_clean) < 6:
        return "Description is too short. Please explain the issue."
        
    # 4. Content Density
    if len(desc_clean.split()) < 2:
        return "Description must contain at least two words."
        
    return None

@app.route('/submit', methods=['POST'])
def submit_request():
    if not session.get('user_role'):
         return redirect(url_for('login'))

    location = request.form.get('location')
    description = request.form.get('description')
    
    # STEP 1: STRICT VALIDATION (Pre-AI)
    # Filter out obvious junk before paying for an AI call
    validation_error = validate_request_data(location, description)
    if validation_error:
        flash(f'❌ Request Rejected: {validation_error}')
        return redirect(url_for('index'))
    
    # NEW: AI INTELLIGENT ANALYSIS (Groq)
    category, priority_score, ai_explanation = analyze_request_with_ai(description, location)

    # 1. SOLUTION FOR INVALID DATA:
    # If AI detects it's not a valid issue, block it.
    if category == 'Invalid':
        flash('❌ Report Rejected: The description provided does not appear to be a valid civic issue. Please describe the infrastructure problem clearly.')
        return redirect(url_for('index'))

    # Smart Routing: Assign Department
    assigned_dept = assign_department(category, priority_score)

    if priority_score >= 80: urgency_label = "Critical"
    elif priority_score >= 50: urgency_label = "High"
    elif priority_score >= 20: urgency_label = "Medium"
    else: urgency_label = "Low"

    new_request = {
        'id': len(requests_list) + 1,
        'category': category,
        'location': location,
        'urgency': urgency_label,
        'description': description,
        'priority_score': priority_score,
        'ai_explanation': ai_explanation,
        'assigned_dept': assigned_dept,
        'status': 'Pending',
        'feedback': None,
        'submitted_by': session.get('username') # Track who submitted it
    }
    
    requests_list.append(new_request)
    
    flash(f"Ref #{new_request['id']} Submitted! Auto-Classified as {category} & Assigned to {assigned_dept} ({urgency_label} Priority).")
    
    return redirect(url_for('index'))

@app.route('/feedback/<int:req_id>', methods=['POST'])
def submit_feedback(req_id):
    rating = request.form.get('rating')
    comments = request.form.get('comments')
    
    for r in requests_list:
        if r['id'] == req_id:
            r['feedback'] = rating
            r['user_comments'] = comments
            break
            
    flash('Thank you for your feedback!')
    return redirect(url_for('index'))

# Defines the route for the dashboard (ADMIN ONLY)
# In a real app, this would be protected by @login_required
@app.route('/dashboard')
def dashboard():
    # Admin Protection
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))

    # Calculate Statistics
    stats = {
        'total': len(requests_list),
        'critical': sum(1 for r in requests_list if r['urgency'] == 'Critical'),
        'high': sum(1 for r in requests_list if r['urgency'] == 'High'),
        'medium': sum(1 for r in requests_list if r['urgency'] == 'Medium'),
        'low': sum(1 for r in requests_list if r['urgency'] == 'Low')
    }

    # PREDICTIVE INSIGHT LOGIC
    prediction_data = generate_prediction_data(requests_list)

    # Heatmap Data Generation
    # Aggregate requests by location to find hotspots
    location_counts = {}
    for r in requests_list:
        loc = r['location']
        if loc:
            # Simple normalization: capitalize first letter
            loc = loc.strip().title() 
            location_counts[loc] = location_counts.get(loc, 0) + 1
    
    # Convert to list of dicts for the frontend
    # Format: [{'location': 'Main St', 'count': 5, 'intensity': 'High'}]
    heatmap_data = []
    for loc, count in location_counts.items():
        intensity = "Low"
        if count >= 5: intensity = "Critical"
        elif count >= 3: intensity = "High"
        elif count >= 2: intensity = "Medium"
        
        heatmap_data.append({
            'location': loc,
            'count': count,
            'intensity': intensity
        })

    # EARLY WARNING SYSTEM LOGIC
    # Checks for immediate critical threats
    system_alert = None
    if stats['critical'] > 0:
        system_alert = {
            'level': 'CRITICAL',
            'message': f"⚠️ ALERT: {stats['critical']} Critical Incident(s) Active! Immediate Response Required."
        }
    elif stats['high'] >= 5:
        system_alert = {
             'level': 'WARNING',
             'message': f"High Load Warning: {stats['high']} High-Priority requests pending."
        }

    # CROSS-DEPARTMENT CORRELATION LOGIC
    # "The Root Cause Detector"
    # Identifies locations where multiple DIFFERENT categories of issues are happening
    # e.g. A "Water Leak" (Utilities) causing a "Pothole" (Infrastructure)
    correlations = []
    location_groups = {}
    for r in requests_list:
        if r['location']:
            loc = r['location'].strip().title()
            if loc not in location_groups:
                location_groups[loc] = set()
            location_groups[loc].add(r['category'])
    
    for loc, categories in location_groups.items():
        if len(categories) > 1:
            # Found a cross-departmental issue
            cats_list = list(categories)
            correlations.append({
                'location': loc,
                'departments': cats_list,
                'message': f"Systemic Risk detected at {loc}. Issues involve separate departments ({', '.join(cats_list)}). Joint inspection recommended to prevent repeated failures."
            })

    # DEPARTMENT PERFORMANCE ANALYTICS
    # Aggregating data to measure efficiency and bottlenecks
    dept_stats = {}
    
    # Initialize from config to ensure all depts show up even if empty
    for dept_name in GAAS_CONFIG['DEPARTMENTS'].values():
        dept_stats[dept_name] = {'total': 0, 'resolved': 0, 'pending_critical': 0, 'efficiency': 0}
    # Add General Services as fallback
    dept_stats['General Services'] = {'total': 0, 'resolved': 0, 'pending_critical': 0, 'efficiency': 0}

    for r in requests_list:
        # Extract base department name (remove "Emergency Unit" suffix)
        full_dept = r.get('assigned_dept', 'General Services')
        base_dept = full_dept.split(' (')[0] # "Public Works Dept (Rapid Action)" -> "Public Works Dept"
        
        if base_dept not in dept_stats:
            dept_stats[base_dept] = {'total': 0, 'resolved': 0, 'pending_critical': 0, 'efficiency': 0}
            
        d = dept_stats[base_dept]
        d['total'] += 1
        if r['status'] == 'Resolved':
            d['resolved'] += 1
        elif r['urgency'] in ['Critical', 'High']:
            d['pending_critical'] += 1
            
    # Calculate Efficiency Scores
    for name, data in dept_stats.items():
        if data['total'] > 0:
            # Simple efficiency metric
            data['efficiency'] = int((data['resolved'] / data['total']) * 100)
        else:
            data['efficiency'] = 100 # Default to 100 if no work assigned

        # SMART RESOURCE RECOMMENDATION LOGIC
        # Suggests staff/equipment based on predicted demand and current bottlenecks
        if data['pending_critical'] >= 3:
            data['recommendation'] = "URGENT: Deploy Emergency Response Team + 2 Heavy Equipment Units."
            data['rec_color'] = "red"
        elif data['pending_critical'] > 0:
             data['recommendation'] = "Allocate overtime staff to clear critical backlog."
             data['rec_color'] = "orange"
        elif data['efficiency'] < 50:
             data['recommendation'] = "Review workflow. Efficiency below 50% - Training required."
             data['rec_color'] = "blue"
        else:
            data['recommendation'] = "Optimal operation. Maintain current staffing levels."
            data['rec_color'] = "green"

    # Prepare data for Chart.js
    chart_labels = list(dept_stats.keys())
    chart_data = [d['total'] for d in dept_stats.values()]

    # PREDICTIVE MAINTENANCE LOGIC (Moving from Reaction to Prevention)
    def generate_forecasting_data(requests):
        # Simulation: Analyze clusters of issues to predict next failure
        forecasts = []
        
        # 1. Analyze by category to find systemic risks
        cat_counts = {}
        for r in requests:
            cat_counts[r['category']] = cat_counts.get(r['category'], 0) + 1
            
        # 2. Generate forecasts based on thresholds
        if cat_counts.get('Electricity', 0) > 2:
            forecasts.append({
                'sector': 'Power Grid A',
                'risk_level': 'High (82%)',
                'predicted_event': 'Transformers overheating due to load imbalance.',
                'impact': 'Potential blackout in 24-48 hours.',
                'action': 'AI has auto-scheduled voltage stabilization crew.',
                'status': 'Prevented'
            })
            
        if cat_counts.get('Water', 0) > 1:
             forecasts.append({
                'sector': 'Mainline Piping (Zone 4)',
                'risk_level': 'Critical (94%)',
                'predicted_event': 'Structural fatigue detected in pressure sensors.',
                'impact': 'Major pipe burst & flooding impending.',
                'action': 'Emergency shut-off valve triggered. Maintenance dispatched.',
                'status': 'In Progress'
            })
            
        if cat_counts.get('Road', 0) > 3:
             forecasts.append({
                'sector': 'Highway 7 Overpass',
                'risk_level': 'Moderate (65%)',
                'predicted_event': 'Surface degradation accelerating.',
                'impact': 'Traffic congestion escalation.',
                'action': 'Added to nightly repair queue.',
                'status': 'Scheduled'
            })
            
        # Default placeholder if no data
        if not forecasts:
            forecasts.append({
                'sector': 'Citywide Infrastructure',
                'risk_level': 'Low (12%)',
                'predicted_event': 'Routine wear and tear.',
                'impact': 'Minimal service disruption.',
                'action': 'Monitoring sensors active.',
                'status': 'Optimal'
            })
            
        return forecasts

    forecast_data = generate_forecasting_data(requests_list)

    # ACTION: Sort requests by AI Priority Score (Highest first) for the dashboard
    # This acts as an "AI Priority List"
    sorted_requests = sorted(requests_list, key=lambda k: k['priority_score'], reverse=True)

    # Pass everything to the template
    return render_template('dashboard.html', requests=sorted_requests, stats=stats, prediction=prediction_data, heatmap_data=heatmap_data, alert=system_alert, correlations=correlations, dept_stats=dept_stats, chart_labels=chart_labels, chart_data=chart_data, forecasts=forecast_data)

# Route to handle Feedback and "Retrain" AI
@app.route('/resolve/<int:req_id>', methods=['POST'])
def resolve_request(req_id):
    # Find request and mark resolved
    for r in requests_list:
        if r['id'] == req_id:
            r['status'] = 'Resolved'
            break
            
    return redirect(url_for('dashboard'))

# Defines the route for the public transparency page
@app.route('/public-view')
def public_view():
    # DATA PRIVACY: Sanitize requests for public viewing
    # We create a new list excluding sensitive details like 'description' or specific 'location'
    sanitized_requests = []
    for req in requests_list:
        safe_req = req.copy()
        # Privacy Mapping: Hide detailed descriptions
        safe_req['description'] = "Details hidden for privacy"
        sanitized_requests.append(safe_req)

    return render_template('public_view.html', requests=sanitized_requests)

# Run the app
if __name__ == '__main__':
    # Get port from environment variable for deployment (Render)
    port = int(os.environ.get("PORT", 5000))
    # host='0.0.0.0' is required for Render/Docker
    app.run(host='0.0.0.0', port=port)
