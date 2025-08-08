import os
import logging
from flask import Flask
from flask_login import LoginManager
from extensions import db, bcrypt
from models import Document
from utils.time_utils import get_ist_time, ist_time_filter  # ✅


app = Flask(__name__)
app.add_template_filter(ist_time_filter, 'ist_time') 


logging.basicConfig(level=logging.DEBUG)


app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///docuflow.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Upload settings
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ROUTED_FOLDER'] = 'uploads/routed'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['ROUTED_FOLDER'], exist_ok=True)

# Init extensions
db.init_app(app)
bcrypt.init_app(app)

login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

def unauthorized():
    return jsonify({"error": "Unauthorized"}), 401

with app.app_context():
    from models import User   # safe NOW, after db.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Ensure/migrate DB
    try:
        db.session.execute(db.text("SELECT user_id FROM document LIMIT 1"))
    except Exception as e:
        if "column" in str(e).lower() and "user_id" in str(e).lower():
            print("Database schema needs updating. Recreating tables...")
            db.drop_all()
            db.create_all()
        else:
            db.create_all()
    else:
        db.create_all()

    # Seed admin
    if not User.query.filter_by(email='admin@docuflow.ai').first():
        admin_user = User(username='admin', email='admin@docuflow.ai', role='admin')
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print("Default admin user created: admin@docuflow.ai / admin123")
        
        # ✅ Register chatbot blueprint here
    from chatbot import chatbot_bp
    app.register_blueprint(chatbot_bp)
# Import routes LAST
from routes import *

if __name__ == "__main__":
    app.run(debug=True)

@app.route('/dismiss/<int:doc_id>', methods=['POST'])

def dismiss_document(doc_id):

    document = Document.query.get_or_404(doc_id)



    if document.status == 'error':

        db.session.delete(document)

        db.session.commit()

        flash('Error document dismissed successfully.', 'success')

    else:

        flash('Only error documents can be dismissed.', 'warning')



    return redirect(url_for('dashboard'))