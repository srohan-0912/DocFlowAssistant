from flask import Blueprint, request, jsonify, session
import requests
import os

chatbot_bp = Blueprint("chatbot", __name__)

# Gemini API setup
API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBISv8ZI4hcTKH5-eHfwEfsMxytyKYBtrg")
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

# Function to fetch real-time dashboard data from backend
def get_dashboard_stats():
    try:
        response = requests.get("http://localhost:5000/api/stats", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": f"Failed to retrieve dashboard stats: {str(e)}"}

@chatbot_bp.route("/chat", methods=["POST"])
def chatbot_response():
    user_input = request.json.get("query", "")
    user_id = session.get("user_id", "default")  # fallback if not logged in
    session_key = f"chat_history_{user_id}"

    if not user_input.strip():
        return jsonify({"response": "Please enter a valid query."})

    # Initialize chat history
    if session_key not in session:
        session[session_key] = []

    # 🔥 Get dashboard data for context
    dashboard_data = get_dashboard_stats()
    if "error" in dashboard_data:
        return jsonify({"response": "Could not fetch dashboard data from backend."})

    # 📊 Format dashboard data into a prompt
    type_dist_str = "\n".join([f"  - {k}: {v}" for k, v in dashboard_data.get("type_distribution", {}).items()])
    context_prompt = f"""
You are an AI assistant for the DocFlow dashboard.
Here are the current dashboard statistics:

- Total Documents: {dashboard_data.get("total_documents", "N/A")}
- Completed Documents: {dashboard_data.get("completed_documents", "N/A")}
- Processing Documents: {dashboard_data.get("processing_documents", "N/A")}
- Error Documents: {dashboard_data.get("error_documents", "N/A")}
- Document Type Distribution:
{type_dist_str}

Use this information to answer the following user query.
"""

    # Build chat history in Gemini format
    history = session[session_key]
    gemini_messages = [{"role": "user", "parts": [{"text": context_prompt.strip()}]}]

    for item in history:
        gemini_messages.append({"role": "user", "parts": [{"text": item["user"]}]})
        gemini_messages.append({"role": "model", "parts": [{"text": item["bot"]}]})

    gemini_messages.append({"role": "user", "parts": [{"text": user_input}]})

    payload = {
        "contents": gemini_messages
    }

    headers = {"Content-Type": "application/json"}

    try:
        res = requests.post(API_URL, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()

        gemini_response = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "Sorry, I couldn't understand that.")
        )

        # Update chat history
        history.append({"user": user_input, "bot": gemini_response})
        session[session_key] = history

        return jsonify({"response": gemini_response})

    except requests.exceptions.Timeout:
        return jsonify({"response": "The request timed out. Please try again."})
    except Exception as e:
        return jsonify({"response": f"Something went wrong: {str(e)}"})
