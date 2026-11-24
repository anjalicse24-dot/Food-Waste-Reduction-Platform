from flask import Flask, request, jsonify, send_from_directory, session
import sqlite3, hashlib, os
from datetime import datetime

app = Flask(__name__, static_folder='.')
app.secret_key = 'feedforward_secret_2024'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DB_PATH = 'feedforward.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fname TEXT NOT NULL, lname TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE, phone TEXT,
            password TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'donor',
            organisation TEXT, city TEXT,
            rating REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_id INTEGER NOT NULL, food_type TEXT NOT NULL,
            quantity TEXT NOT NULL, location TEXT NOT NULL,
            category TEXT DEFAULT 'Other', expiry_time TEXT,
            notes TEXT, image_url TEXT,
            urgency TEXT DEFAULT 'low', status TEXT DEFAULT 'available',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (donor_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donation_id INTEGER NOT NULL UNIQUE, ngo_id INTEGER NOT NULL,
            claimed_at TEXT DEFAULT (datetime('now')), completed_at TEXT,
            FOREIGN KEY (donation_id) REFERENCES donations(id),
            FOREIGN KEY (ngo_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donation_id INTEGER NOT NULL, ngo_id INTEGER NOT NULL,
            donor_id INTEGER NOT NULL, rating INTEGER NOT NULL,
            comment TEXT, created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(donation_id, ngo_id)
        );
    ''')
    pw = hashlib.sha256('password123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (fname,lname,email,phone,password,role,organisation,city) VALUES (?,?,?,?,?,?,?,?)",
              ('Anjali','Sharma','donor@demo.com','9876543210',pw,'donor','Rajdhani Restaurant','Bangalore'))
    c.execute("INSERT OR IGNORE INTO users (fname,lname,email,phone,password,role,organisation,city) VALUES (?,?,?,?,?,?,?,?)",
              ('Akshaya','Patra','ngo@demo.com','9876543211',pw,'ngo','Akshaya Patra','Bangalore'))
    c.execute("INSERT OR IGNORE INTO users (fname,lname,email,phone,password,role,organisation,city) VALUES (?,?,?,?,?,?,?,?)",
              ('Super','Admin','admin@demo.com','9876543212',pw,'admin','FeedForward HQ','Bangalore'))
    c.execute("SELECT COUNT(*) FROM donations")
    if c.fetchone()[0] == 0:
        seeds = [
            (1,'Biryani','40 portions','Koramangala, Bangalore','Cooked Meal','high','available'),
            (1,'Mixed Salad','15 Kg','Indiranagar, Bangalore','Cooked Meal','medium','available'),
            (1,'Bread Loaves','30 units','Whitefield, Bangalore','Bakery','low','available'),
            (1,'Dal & Rice','25 portions','HSR Layout, Bangalore','Cooked Meal','high','claimed'),
            (1,'Cakes & Pastries','50 units','MG Road, Bangalore','Bakery','high','completed'),
            (1,'South Indian Thali','60 portions','BTM Layout, Bangalore','Cooked Meal','medium','available'),
            (1,'Fresh Vegetables','20 Kg','JP Nagar, Bangalore','Raw Vegetables','low','available'),
        ]
        for s in seeds:
            c.execute("INSERT INTO donations (donor_id,food_type,quantity,location,category,urgency,status) VALUES (?,?,?,?,?,?,?)", s)
    conn.commit(); conn.close()

init_db()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def rows_to_list(rows): return [dict(r) for r in rows]
def row_to_dict(row): return dict(row) if row else None

@app.route('/')
def index(): return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_file(filename):
    if os.path.exists(filename): return send_from_directory('.', filename)
    if os.path.exists(filename + '.html'): return send_from_directory('.', filename + '.html')
    return "Not found", 404

@app.route('/api/register', methods=['POST'])
def register():
    d = request.get_json()
    fname,lname = d.get('fname','').strip(), d.get('lname','').strip()
    email,phone = d.get('email','').strip().lower(), d.get('phone','').strip()
    password,role = d.get('password',''), d.get('role','donor')
    org,city = d.get('org','').strip(), d.get('city','').strip()
    if not all([fname,lname,email,password]):
        return jsonify({'success':False,'message':'All fields required'}),400
    conn = get_db()
    try:
        if conn.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone():
            return jsonify({'success':False,'message':'Email already registered'}),409
        conn.execute('INSERT INTO users (fname,lname,email,phone,password,role,organisation,city) VALUES (?,?,?,?,?,?,?,?)',
                     (fname,lname,email,phone,hash_pw(password),role,org,city))
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        session.update({'user_id':user['id'],'role':role,'name':f'{fname} {lname}'})
        return jsonify({'success':True,'role':role,'name':f'{fname} {lname}','user_id':user['id']})
    except Exception as e: return jsonify({'success':False,'message':str(e)}),500
    finally: conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    d = request.get_json()
    email,password = d.get('email','').strip().lower(), d.get('password','')
    if not email or not password: return jsonify({'success':False,'message':'Required'}),400
    conn = get_db()
    try:
        user = conn.execute('SELECT * FROM users WHERE email=? AND password=?',(email,hash_pw(password))).fetchone()
        if not user: return jsonify({'success':False,'message':'Invalid credentials'}),401
        session.update({'user_id':user['id'],'role':user['role'],'name':f"{user['fname']} {user['lname']}"})
        return jsonify({'success':True,'role':user['role'],'name':session['name'],'user_id':user['id']})
    finally: conn.close()

@app.route('/api/logout', methods=['POST'])
def logout(): session.clear(); return jsonify({'success':True})

@app.route('/api/me')
def me():
    uid = session.get('user_id')
    if not uid: return jsonify({'success':False}),401
    conn = get_db()
    u = conn.execute('SELECT id,fname,lname,email,role,organisation,city,rating FROM users WHERE id=?',(uid,)).fetchone()
    conn.close()
    return jsonify({'success':True,'user':row_to_dict(u)})

@app.route('/api/donate', methods=['POST'])
def post_donation():
    d = request.get_json()
    donor_id = session.get('user_id',1)
    food_type,quantity = d.get('food_type','').strip(), d.get('quantity','').strip()
    location,category = d.get('location','').strip(), d.get('category','Other')
    expiry,notes,image_url = d.get('expiry_time',''), d.get('notes',''), d.get('image_url','')
    if not all([food_type,quantity,location]):
        return jsonify({'success':False,'message':'food_type, quantity and location required'}),400
    urgency = 'low'
    if expiry:
        try:
            diff = (datetime.fromisoformat(expiry) - datetime.now()).total_seconds()/3600
            urgency = 'high' if diff<3 else ('medium' if diff<8 else 'low')
        except: pass
    conn = get_db()
    try:
        conn.execute('INSERT INTO donations (donor_id,food_type,quantity,location,category,expiry_time,notes,image_url,urgency,status) VALUES (?,?,?,?,?,?,?,?,?,?)',
                     (donor_id,food_type,quantity,location,category,expiry or None,notes,image_url,urgency,'available'))
        conn.commit()
        did = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        return jsonify({'success':True,'donation_id':did,'urgency':urgency})
    except Exception as e: return jsonify({'success':False,'message':str(e)}),500
    finally: conn.close()

@app.route('/api/donations')
def get_donations():
    city,category,urgency = request.args.get('city',''), request.args.get('category',''), request.args.get('urgency','')
    conn = get_db()
    try:
        q = "SELECT d.*,u.fname,u.lname,u.organisation,u.city as donor_city FROM donations d JOIN users u ON d.donor_id=u.id WHERE d.status='available'"
        p = []
        if city:     q+=' AND u.city=?';     p.append(city)
        if category: q+=' AND d.category=?'; p.append(category)
        if urgency:  q+=' AND d.urgency=?';  p.append(urgency)
        q+=" ORDER BY CASE d.urgency WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, d.created_at DESC"
        return jsonify({'success':True,'donations':rows_to_list(conn.execute(q,p).fetchall())})
    finally: conn.close()

@app.route('/api/my-donations')
def my_donations():
    conn = get_db()
    try:
        rows = conn.execute('''SELECT d.*,u2.organisation as claimer_org FROM donations d
            LEFT JOIN claims c ON d.id=c.donation_id LEFT JOIN users u2 ON c.ngo_id=u2.id
            WHERE d.donor_id=? ORDER BY d.created_at DESC''',(session.get('user_id',1),)).fetchall()
        return jsonify({'success':True,'donations':rows_to_list(rows)})
    finally: conn.close()

@app.route('/api/claim', methods=['POST'])
def claim_donation():
    d = request.get_json()
    ngo_id,donation_id = session.get('user_id',2), d.get('donation_id')
    if not donation_id: return jsonify({'success':False,'message':'donation_id required'}),400
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM donations WHERE id=? AND status='available'",(donation_id,)).fetchone():
            return jsonify({'success':False,'message':'Not available'}),409
        conn.execute("UPDATE donations SET status='claimed' WHERE id=?",(donation_id,))
        conn.execute("INSERT INTO claims (donation_id,ngo_id) VALUES (?,?)",(donation_id,ngo_id))
        conn.commit()
        return jsonify({'success':True})
    except Exception as e: return jsonify({'success':False,'message':str(e)}),500
    finally: conn.close()

@app.route('/api/complete', methods=['POST'])
def complete_donation():
    d = request.get_json()
    conn = get_db()
    try:
        conn.execute("UPDATE donations SET status='completed' WHERE id=?",(d.get('donation_id'),))
        conn.execute("UPDATE claims SET completed_at=datetime('now') WHERE donation_id=?",(d.get('donation_id'),))
        conn.commit(); return jsonify({'success':True})
    finally: conn.close()

@app.route('/api/my-claims')
def my_claims():
    conn = get_db()
    try:
        rows = conn.execute('''SELECT d.*,c.claimed_at,c.completed_at,u.fname,u.lname,u.organisation
            FROM claims c JOIN donations d ON c.donation_id=d.id JOIN users u ON d.donor_id=u.id
            WHERE c.ngo_id=? ORDER BY c.claimed_at DESC''',(session.get('user_id',2),)).fetchall()
        return jsonify({'success':True,'claims':rows_to_list(rows)})
    finally: conn.close()

@app.route('/api/rate', methods=['POST'])
def rate():
    d = request.get_json()
    ngo_id,donation_id,rating,comment = session.get('user_id',2),d.get('donation_id'),d.get('rating'),d.get('comment','')
    if not donation_id or not rating: return jsonify({'success':False}),400
    conn = get_db()
    try:
        don = conn.execute('SELECT donor_id FROM donations WHERE id=?',(donation_id,)).fetchone()
        if not don: return jsonify({'success':False,'message':'Not found'}),404
        conn.execute('INSERT OR REPLACE INTO ratings (donation_id,ngo_id,donor_id,rating,comment) VALUES (?,?,?,?,?)',
                     (donation_id,ngo_id,don['donor_id'],rating,comment))
        avg = conn.execute('SELECT AVG(rating) FROM ratings WHERE donor_id=?',(don['donor_id'],)).fetchone()[0]
        conn.execute('UPDATE users SET rating=? WHERE id=?',(round(avg,2),don['donor_id']))
        conn.commit(); return jsonify({'success':True})
    finally: conn.close()

@app.route('/api/admin/stats')
def admin_stats():
    conn = get_db()
    try:
        return jsonify({'success':True,'stats':{
            'total_donations': conn.execute("SELECT COUNT(*) FROM donations").fetchone()[0],
            'completed':       conn.execute("SELECT COUNT(*) FROM donations WHERE status='completed'").fetchone()[0],
            'total_users':     conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            'total_ngos':      conn.execute("SELECT COUNT(*) FROM users WHERE role='ngo'").fetchone()[0],
            'avg_rating': round(conn.execute("SELECT COALESCE(AVG(rating),0) FROM ratings").fetchone()[0],1)
        }})
    finally: conn.close()

@app.route('/api/admin/users')
def admin_users():
    conn = get_db()
    try:
        rows = conn.execute('SELECT id,fname,lname,email,role,organisation,city,rating,created_at FROM users ORDER BY created_at DESC').fetchall()
        return jsonify({'success':True,'users':rows_to_list(rows)})
    finally: conn.close()

@app.route('/api/admin/donations')
def admin_donations():
    conn = get_db()
    try:
        rows = conn.execute('SELECT d.*,u.fname,u.lname,u.organisation FROM donations d JOIN users u ON d.donor_id=u.id ORDER BY d.created_at DESC LIMIT 50').fetchall()
        return jsonify({'success':True,'donations':rows_to_list(rows)})
    finally: conn.close()

@app.route('/api/admin/delete-donation/<int:did>', methods=['DELETE'])
def admin_del_donation(did):
    conn = get_db()
    try: conn.execute('DELETE FROM donations WHERE id=?',(did,)); conn.commit(); return jsonify({'success':True})
    finally: conn.close()

@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files: return jsonify({'success':False}),400
    f = request.files['file']
    ext = f.filename.rsplit('.',1)[-1].lower()
    if ext not in {'jpg','jpeg','png','gif','webp'}: return jsonify({'success':False,'message':'Invalid type'}),400
    fname = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"
    f.save(os.path.join(UPLOAD_FOLDER,fname))
    return jsonify({'success':True,'url':f'/static/uploads/{fname}'})

if __name__ == '__main__':
    print("\n🌿 FeedForward server starting...")
    print("📍 Open: http://localhost:5000")
    print("─────────────────────────────────")
    print("  Donor → donor@demo.com / password123")
    print("  NGO   → ngo@demo.com   / password123")
    print("  Admin → admin@demo.com / password123")
    print("─────────────────────────────────\n")
    app.run(debug=True, port=5000)