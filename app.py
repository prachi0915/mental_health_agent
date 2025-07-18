import os
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import google.generativeai as genai
import random
import sqlite3
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Flask
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mindmate_secret")

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# Base system instruction
SYSTEM_PROMPT = """
You are MindMate, a friendly and empathetic AI companion dedicated to mental wellness. 
Always be calm, warm, and non-judgmental. Respond to user concerns with compassion and support.
You can offer:
- Mood check-ins
- Affirmations
- Breathing exercises
- Journaling prompts
- Self-care suggestions
If user expresses distress, suggest contacting a professional or helpline.
"""

# --- Mood Tracking Setup ---
DB_PATH = os.path.join(os.path.dirname(__file__), 'mood.db')

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS moods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mood TEXT NOT NULL,
            source TEXT DEFAULT 'manual',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()

init_db()

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json['message']
    # Safety pre-check for distress keywords
    distress_keywords = ["suicide", "kill myself", "end my life", "self-harm", "hurt myself"]
    if any(keyword in user_input.lower() for keyword in distress_keywords):
        return jsonify({'response': "You're not alone. Please speak to a mental health professional or call a local helpline. You matter."})
    # Use latest mood in prompt if available
    mood = session.get('latest_mood')
    detected_mood = None
    # If no manual mood, detect from chat
    if not mood:
        mood_detect_prompt = (
            "You are a mood detection assistant. "
            "Given the following user message, respond ONLY with the most appropriate mood emoji from this list: "
            "😊 (happy), 😐 (neutral), 😔 (sad), 😠 (angry), 😰 (anxious), 😴 (tired), 😇 (grateful). "
            "Message: '" + user_input + "'"
        )
        try:
            mood_response = model.generate_content(mood_detect_prompt)
            detected_mood = mood_response.text.strip().split()[0]  # Get the emoji
            if detected_mood in ["😊", "😐", "😔", "😠", "😰", "😴", "😇"]:
                mood = detected_mood
                session['latest_mood'] = mood
                # Save detected mood to DB
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute('INSERT INTO moods (mood, source) VALUES (?, ?)', (mood, 'detected'))
                    conn.commit()
        except Exception as e:
            detected_mood = None
    mood_context = f"\nUser's current mood: {mood}" if mood else ""
    prompt = f"{SYSTEM_PROMPT}{mood_context}\nUser: {user_input}\nMindMate:"
    try:
        response = model.generate_content(prompt)
        reply = response.text.strip()
        return jsonify({'response': reply, 'detected_mood': detected_mood})
    except Exception as e:
        return jsonify({'response': "Sorry, I'm having trouble responding right now."})

@app.route('/mood', methods=['POST'])
def save_mood():
    mood = request.json.get('mood')
    if not mood:
        return jsonify({'success': False, 'error': 'No mood provided'}), 400
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('INSERT INTO moods (mood, source) VALUES (?, ?)', (mood, 'manual'))
        conn.commit()
    session['latest_mood'] = mood
    # Mood-specific greeting and suggestion
    mood_greetings = {
        "😊": "I'm glad to hear you're feeling happy! Let's keep the positivity going.",
        "😐": "Thanks for sharing your mood. I'm here if you want to talk or reflect.",
        "😔": "I'm sorry you're feeling sad. I'm here to listen and support you.",
        "😠": "It's okay to feel angry sometimes. Let's find a way to process those feelings together.",
        "😰": "Anxiety can be tough. Would you like to try a calming exercise?",
        "😴": "Feeling tired is a sign to take it easy. Remember to rest and care for yourself.",
        "😇": "Gratitude is wonderful! Would you like to reflect on what you're grateful for today?"
    }
    mood_suggestions = {
        "😊": "Celebrate your happiness! Maybe share your joy with someone or write down what made you smile today.",
        "😐": "How about a quick check-in? Try journaling a few thoughts or taking a mindful breath.",
        "😔": "Would you like to try a positive affirmation or write about your feelings in a journal?",
        "😠": "Try a grounding exercise: take a deep breath, count to five, and notice your surroundings.",
        "😰": "Let's do a 4-7-8 breathing exercise together: inhale for 4, hold for 7, exhale for 8.",
        "😴": "A short stretch or a glass of water might help. Remember, rest is important!",
        "😇": "List three things you're grateful for today, or send a thank-you message to someone."
    }
    greeting = mood_greetings.get(mood, "Thank you for sharing your mood.")
    suggestion = mood_suggestions.get(mood, None)
    return jsonify({'success': True, 'greeting': greeting, 'suggestion': suggestion})

@app.route('/mood/history', methods=['GET'])
def get_mood_history():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT mood, source, timestamp FROM moods ORDER BY timestamp DESC LIMIT 30')
        moods = [{'mood': row[0], 'source': row[1], 'timestamp': row[2]} for row in c.fetchall()]
    return jsonify({'moods': moods})

# --- Daily Tips ---
DAILY_TIPS = [
    "Take a deep breath and notice how you feel.",
    "Write down three things you're grateful for today.",
    "Go for a short walk and observe your surroundings.",
    "Drink a glass of water and stretch your body.",
    "Reach out to a friend or loved one just to say hi.",
    "Try a 4-7-8 breathing exercise.",
    "Listen to your favorite song and relax.",
    "Take a mindful moment: close your eyes and focus on your breath.",
    "Give yourself permission to rest today.",
    "Remember: progress, not perfection."
]
@app.route('/mood/reset', methods=['POST'])
def reset_mood():
    session.pop('latest_mood', None)
    return jsonify({'success': True})

@app.route('/daily-tip', methods=['GET'])
def daily_tip():
    tip = random.choice(DAILY_TIPS)
    return jsonify({'tip': tip})

if __name__ == '__main__':
    app.run(debug=True, port=5000)