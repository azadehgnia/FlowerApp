import os  
from flask import Flask, request, redirect, render_template, url_for, session, flash  
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user  
import psycopg2  
from werkzeug.utils import secure_filename  
from azure.storage.blob import BlobServiceClient  
from azure.storage.blob import generate_blob_sas, BlobSasPermissions
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv  

  
import os  
SECRET_KEY = os.getenv("SECRET_KEY")  
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  

load_dotenv(os.path.join(BASE_DIR, "env", ".env"))

# App setup  
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"), static_folder=os.path.join(BASE_DIR, "static"))
app.secret_key = 'YOUR_FLASK_SECRET_KEY'  # <<<< set this!  
  
# Flask-Login setup  
login_manager = LoginManager()  
login_manager.init_app(app)  
  
# Dummy users for demo; replace with your user logic or DB!  
users = {  
    "testuser": {"password": "testpass"}  
}  
  
class User(UserMixin):  
    def __init__(self, username):  
        self.id = username  
  
@login_manager.user_loader  
def load_user(user_id):  
    if user_id in users:  
        return User(user_id)  
    return None  
  
# Azure PostgreSQL connection info  
DB_HOST = os.getenv("DB_HOST")  
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER") 
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")

print("DB_HOST:", DB_HOST)
  
def get_db_connection():  
    return psycopg2.connect(  
        host=DB_HOST,  
        dbname=DB_NAME,  
        user=DB_USER,  
        password=DB_PASS,
        port=DB_PORT
    )  
  
# Azure Blob Storage connection  
# filepath: c:\Code\FlowerApp\app.py
try:
    AZURE_BLOB_CONN_STR = os.getenv("AZURE_BLOB_CONN_STR")
    BLOB_CONTAINER = os.getenv("BLOB_CONTAINER")
    print("AZURE_BLOB_CONN_STR:", AZURE_BLOB_CONN_STR)

    blob_service_client = BlobServiceClient.from_connection_string(AZURE_BLOB_CONN_STR)
    container_client = blob_service_client.get_container_client(BLOB_CONTAINER)
except Exception as e:
    print("Azure Blob connection error:", e)


### ROUTES ###  
  
@app.route('/')  
def index():  
    if current_user.is_authenticated:  
        # Show upload form and user's flowers  
        conn = get_db_connection()  
        cur = conn.cursor()  
        cur.execute("SELECT name, image_url FROM flowers WHERE user_id=%s ORDER BY created_at DESC", (current_user.id,))  
        flowers = cur.fetchall()  
        cur.close()  
        conn.close()  
        return render_template('dashboard.html', flowers=flowers)  
    else:  
        return redirect(url_for('login'))  
  
@app.route('/login', methods=['GET', 'POST'])  
def login():  
    if request.method == 'POST':  
        user = request.form['username']  
        pw = request.form['password']  
        if user in users and users[user]['password'] == pw:  
            login_user(User(user))  
            return redirect(url_for('index'))  
        flash("Invalid credentials")  
    return render_template('login.html')  
  
@app.route('/logout')  
@login_required  
def logout():  
    logout_user()  
    return redirect(url_for('login'))  

@app.route('/create')
def create():
    return render_template('create.html')

@app.route('/upload', methods=['POST'])  
@login_required  
def upload():  
    flower_name = request.form.get('flower_name')  
    image = request.files.get('flower_image')  
  
    if not flower_name or not image:  
        flash("Name and image required")  
        return redirect(url_for('index'))  
  
    # Secure filename and generate a unique filename  
    filename = secure_filename(image.filename)  
    unique_name = str(uuid.uuid4()) + "_" + filename  
  
    # Upload to Azure Blob Storage  
    blob_client = container_client.get_blob_client(unique_name)  
    image.seek(0)
    try:
        blob_client.upload_blob(image, overwrite=True)
        image_url = blob_client.url
    except Exception as e:
        flash(f"Failed to upload image: {e}")
        return redirect(url_for('index'))

    # Save flower info to database
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO flowers (user_id, name, image_url) VALUES (%s, %s, %s)",
        (current_user.id, flower_name, image_url)
    )
    conn.commit()
    cur.close()
    conn.close()

    flash("Flower uploaded successfully!")
    return redirect(url_for('index'))

@app.route('/explore')
def explore():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, image_url FROM flowers ORDER BY created_at DESC")
    flowers = cur.fetchall()
    cur.close()
    conn.close()

      # Generate SAS URLs for each image
      #for the SAS to work allow network connectivity and allow key access.
    sas_flowers = []
    for name, image_url in flowers:
        blob_name = image_url.split('/')[-1]
        sas_token = generate_blob_sas(
            account_name=blob_service_client.account_name,
            container_name=BLOB_CONTAINER,
            blob_name=blob_name,
            account_key=blob_service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        sas_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER}/{blob_name}?{sas_token}"
        sas_flowers.append((name, sas_url))

    return render_template('explore_flowers.html', flowers=sas_flowers)