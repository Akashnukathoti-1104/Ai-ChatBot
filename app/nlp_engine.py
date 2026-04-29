import re
import time
import os
import json
import random
from typing import Tuple, List, Dict
from datetime import datetime

# ── Optional heavy deps (graceful fallback) ──────────────────────────────────
try:
    import nltk
    from nltk.tokenize import word_tokenize
    from nltk.corpus import stopwords
    from nltk.stem import WordNetLemmatizer
    nltk.download('punkt', quiet=True)
    nltk.download('punkt_tab', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
    NLTK_AVAILABLE = True
except Exception:
    NLTK_AVAILABLE = False

try:
    from transformers import pipeline
    _sentiment = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
    TRANSFORMERS_AVAILABLE = True
except Exception:
    TRANSFORMERS_AVAILABLE = False

# ── Knowledge Base ─────────────────────────────────────────────────────────
KNOWLEDGE_BASE: Dict[str, Dict] = {
    "greeting": {
        "patterns": ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "howdy", "greetings", "sup", "what's up"],
        "responses": [
            "👋 Hello! I'm NexusAI, your intelligent assistant. How can I help you today?",
            "Hey there! Great to see you. What can I do for you?",
            "Hi! I'm ready to help. What's on your mind?",
            "Hello! Welcome. Feel free to ask me anything!"
        ],
        "follow_up": "You can ask me about our services, pricing, technical support, or anything else!"
    },
    "farewell": {
        "patterns": ["bye", "goodbye", "see you", "take care", "later", "cya", "farewell", "quit", "exit"],
        "responses": [
            "Goodbye! Have a wonderful day! 👋",
            "See you later! Don't hesitate to come back if you need anything!",
            "Take care! It was a pleasure chatting with you! 😊",
            "Bye! Feel free to return anytime you need help!"
        ]
    },
    "thanks": {
        "patterns": ["thank", "thanks", "appreciate", "grateful", "cheers", "ty", "thx"],
        "responses": [
            "You're welcome! Happy to help anytime! 😊",
            "My pleasure! Is there anything else I can assist you with?",
            "Glad I could help! Don't hesitate to ask if you need more assistance.",
            "Anytime! That's what I'm here for! 🌟"
        ]
    },
    "pricing": {
        "patterns": ["price", "cost", "pricing", "fee", "charge", "plan", "subscription", "how much", "affordable", "budget"],
        "responses": [
            "💰 Our pricing plans:\n\n• **Free**: 100 messages/month — Perfect for trying out\n• **Starter** ($9/mo): 1,000 messages + analytics\n• **Pro** ($29/mo): Unlimited messages + priority support\n• **Enterprise**: Custom pricing for large teams\n\nAll paid plans include a 14-day free trial!",
            "We offer flexible pricing to suit all needs:\n\n🆓 **Free Plan** — Great for individuals\n🚀 **Starter ($9/mo)** — For small teams\n💼 **Pro ($29/mo)** — For growing businesses\n🏢 **Enterprise** — Contact us for custom pricing"
        ]
    },
    "features": {
        "patterns": ["feature", "capability", "can you", "what do you do", "able to", "function", "support", "help with"],
        "responses": [
            "🚀 Here's what I can do for you:\n\n• 💬 **Natural conversations** with context memory\n• 🎯 **Intent detection** to understand your needs\n• 📊 **Analytics dashboard** to track interactions\n• 🔍 **FAQ answering** from knowledge base\n• 🌐 **Multi-topic support** — technical, sales, general\n• ⚡ **Fast responses** with 99.9% uptime\n\nWhat would you like to explore?",
        ]
    },
    "technical": {
        "patterns": ["bug", "error", "issue", "problem", "not working", "broken", "crash", "fix", "troubleshoot", "debug", "help"],
        "responses": [
            "🔧 I'm here to help with technical issues! Please describe what you're experiencing:\n\n1. What were you trying to do?\n2. What happened instead?\n3. Any error messages?\n\nThe more details you share, the better I can assist!",
            "Sorry to hear you're having trouble! Let's troubleshoot together. Can you share:\n• The exact error message (if any)\n• What steps led to the issue\n• Which browser/device you're using"
        ]
    },
    "about": {
        "patterns": ["who are you", "what are you", "about you", "tell me about", "your name", "introduce yourself"],
        "responses": [
            "🤖 I'm **NexusAI** — an intelligent chatbot powered by NLP and machine learning.\n\nI'm built with:\n• 🐍 Python + FastAPI backend\n• 🧠 NLTK for natural language processing\n• 💾 SQLite for conversation logging\n• ⚡ Real-time responses with intent recognition\n\nI'm here to make your experience seamless and helpful!",
        ]
    },
    "human": {
        "patterns": ["human", "real person", "agent", "representative", "speak to someone", "live chat", "talk to a person"],
        "responses": [
            "👤 I understand you'd like to speak with a human agent.\n\nYou can reach our team via:\n• 📧 **Email**: support@nexusai.com\n• 📞 **Phone**: +1 (555) 123-4567\n• 🕐 **Hours**: Mon–Fri, 9AM–6PM EST\n\nIn the meantime, I'll do my best to help you!"
        ]
    },
    "hours": {
        "patterns": ["hours", "open", "available", "when", "schedule", "time", "working hours"],
        "responses": [
            "🕐 **Our availability:**\n\n• 🤖 **AI Chatbot (me!)**: 24/7, always here!\n• 👤 **Human Support**: Mon–Fri, 9AM–6PM EST\n• 📧 **Email**: Responses within 24 hours\n\nI'm always available to help you!"
        ]
    },
    "refund": {
        "patterns": ["refund", "money back", "cancel", "cancellation", "return", "dispute"],
        "responses": [
            "💳 **Refund & Cancellation Policy:**\n\n• Cancel anytime — no long-term contracts\n• Full refund within **14 days** of purchase\n• Prorated refunds for annual plans\n• No questions asked!\n\nTo initiate a refund, email billing@nexusai.com or I can escalate this to our billing team."
        ]
    },
    "default": {
        "responses": [
            "🤔 That's an interesting question! I'm not sure I have the perfect answer, but let me try to help. Could you rephrase or provide more context?",
            "I want to make sure I understand correctly. Could you elaborate a bit more on what you need?",
            "Hmm, I'm not entirely sure about that specific topic. For complex questions, our human team at support@nexusai.com can help. Is there something else I can assist with?",
            "Great question! I'm still learning about that topic. Could you ask me something about our services, pricing, or technical support?"
        ]
    }
}

# ── NLP Utilities ──────────────────────────────────────────────────────────
def preprocess_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    if NLTK_AVAILABLE:
        try:
            tokens = word_tokenize(text)
            lemmatizer = WordNetLemmatizer()
            stop_words = set(stopwords.words('english')) - {'not', 'no', 'never', 'help', 'please'}
            tokens = [lemmatizer.lemmatize(t) for t in tokens if t not in stop_words]
            return ' '.join(tokens)
        except Exception:
            pass
    return text

def detect_intent(text: str) -> Tuple[str, float]:
    processed = preprocess_text(text)
    text_lower = text.lower()
    
    best_intent = "default"
    best_score = 0.0

    for intent, data in KNOWLEDGE_BASE.items():
        if intent == "default":
            continue
        patterns = data.get("patterns", [])
        score = 0.0
        for pattern in patterns:
            if pattern in text_lower:
                # Exact match bonus
                score += 1.0 if pattern == text_lower else 0.8
            elif pattern in processed:
                score += 0.6
            # Partial word match
            elif any(word in text_lower.split() for word in pattern.split()):
                score += 0.3

        if patterns:
            score = score / len(patterns) * 3  # normalize + amplify
        
        if score > best_score:
            best_score = score
            best_intent = intent

    confidence = min(0.99, best_score) if best_score > 0.2 else 0.4
    if best_score <= 0.2:
        best_intent = "default"

    return best_intent, round(confidence, 2)

def get_sentiment(text: str) -> str:
    if TRANSFORMERS_AVAILABLE:
        try:
            result = _sentiment(text[:512])[0]
            return result['label'].lower()
        except Exception:
            pass
    # Simple rule-based fallback
    negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'angry', 'frustrated', 'upset']
    positive_words = ['good', 'great', 'awesome', 'love', 'excellent', 'amazing', 'happy']
    text_lower = text.lower()
    neg = sum(1 for w in negative_words if w in text_lower)
    pos = sum(1 for w in positive_words if w in text_lower)
    if neg > pos:
        return "negative"
    elif pos > neg:
        return "positive"
    return "neutral"

def build_response(intent: str, sentiment: str, history: List[Dict]) -> str:
    data = KNOWLEDGE_BASE.get(intent, KNOWLEDGE_BASE["default"])
    responses = data.get("responses", KNOWLEDGE_BASE["default"]["responses"])
    response = random.choice(responses)
    
    # Empathy for negative sentiment
    if sentiment == "negative" and intent not in ["farewell"]:
        empathy = random.choice([
            "I understand your frustration, and I'm here to help. ",
            "I'm sorry you're having a difficult time. Let me assist you. ",
            "I hear you — let's get this sorted out together. "
        ])
        response = empathy + response

    # Add follow-up for greeting
    if intent == "greeting" and "follow_up" in data:
        response += f"\n\n{data['follow_up']}"

    return response

# ── Main Chat Function ─────────────────────────────────────────────────────
def generate_response(user_message: str, session_history: List[Dict]) -> Dict:
    start_time = time.time()
    
    intent, confidence = detect_intent(user_message)
    sentiment = get_sentiment(user_message)
    response = build_response(intent, sentiment, session_history)
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    return {
        "response": response,
        "intent": intent,
        "confidence": confidence,
        "sentiment": sentiment,
        "response_time_ms": elapsed_ms,
        "timestamp": datetime.utcnow().isoformat()
    }
