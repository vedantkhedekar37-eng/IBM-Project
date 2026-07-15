# ArogyaAi — IBM Watsonx.ai Nutrition Chatbot
# Deployment Instructions

---

## 🌿 Overview

**ArogyaAi** is an AI-powered nutrition chatbot built with:
- **Backend**: Python Flask 3 + `ibm-watsonx-ai` SDK
- **AI Model**: IBM Granite (via IBM Watsonx.ai)
- **Frontend**: Bootstrap 5, Vanilla JS, responsive SPA

---

## 📁 Project Structure

```
ArogyaAi/
├── app.py                  ← Flask backend + AGENT_INSTRUCTIONS
├── requirements.txt        ← Python dependencies
├── .env.example            ← Environment variable template
├── .env                    ← Your secrets (gitignore this!)
├── templates/
│   └── index.html          ← Full SPA frontend
├── Procfile                ← Heroku/Railway deployment
├── runtime.txt             ← Python version for cloud
└── README.md               ← This file
```

---

## 🔑 Step 1 — Get IBM Cloud Credentials

1. Sign up / log in at [cloud.ibm.com](https://cloud.ibm.com)
2. Create an **IBM Watsonx.ai** service instance
3. Go to **Manage → Access (IAM) → API keys** → Create an API key
4. Open your Watsonx.ai project → **Manage → General** → Copy the **Project ID**
5. Note your **service URL** (e.g. `https://us-south.ml.cloud.ibm.com`)

---

## ⚙️ Step 2 — Configure Environment

```bash
cd ArogyaAi

# Copy the example env file
cp .env.example .env

# Edit .env and fill in your credentials
notepad .env        # Windows
nano .env           # Linux/Mac
```

Required values in `.env`:

```
IBM_API_KEY=your_ibm_cloud_api_key_here
IBM_PROJECT_ID=your_watsonx_project_id_here
IBM_URL=https://us-south.ml.cloud.ibm.com
MODEL_ID=ibm/granite-13b-chat-v2
FLASK_SECRET_KEY=any-random-string-here
```

---

## 🐍 Step 3 — Local Setup & Run

### Create virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run development server

```bash
python app.py
```

Open your browser at: **http://localhost:5000**

---

## 🤖 Step 4 — Customize Agent Behavior

Open `app.py` and find the `AGENT_INSTRUCTIONS` section (lines ~25–85):

```python
AGENT_INSTRUCTIONS = """
You are ArogyaAi, a compassionate and knowledgeable AI nutrition assistant...
"""
```

You can customize:

| Section | What to change |
|---|---|
| `PERSONA & TONE` | Name, language style, communication approach |
| `SPECIALIZATIONS` | Regional cuisines, medical conditions, diet types |
| `NUTRITION GUIDELINES` | Reference standards, superfoods, food combos |
| `FAMILY PROFILE HANDLING` | Age groups, special conditions, unified meals |
| `MEAL PLANNING FORMAT` | Meal structure, frequency, portion sizes |
| `SAFETY RULES` | Medical disclaimers, calorie limits, allergens |
| `RESPONSE STYLE` | Format, length, emoji usage, tips |

---

## 🚀 Step 5 — Production Deployment

### Option A: Gunicorn (Linux VPS / Docker)

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Option B: Heroku

```bash
# Create Procfile (already provided)
heroku create arogya-ai-app
heroku config:set IBM_API_KEY=your_key
heroku config:set IBM_PROJECT_ID=your_project_id
heroku config:set IBM_URL=https://us-south.ml.cloud.ibm.com
heroku config:set MODEL_ID=ibm/granite-13b-chat-v2
heroku config:set FLASK_SECRET_KEY=your-secret
git push heroku main
```

### Option C: Railway / Render

1. Push to GitHub
2. Connect repo to Railway/Render
3. Set environment variables in dashboard
4. Deploy automatically on push

### Option D: Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:app"]
```

```bash
docker build -t arogya-ai .
docker run -p 5000:5000 --env-file .env arogya-ai
```

---

## 🔧 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | GET | Serve the web app |
| `/api/chat` | POST | Send a chat message |
| `/api/bmi` | POST | Calculate BMI |
| `/api/calories` | POST | Calculate TDEE & macros |
| `/api/meal-plan` | POST | Generate 7-day meal plan |
| `/api/analyze-food` | POST | Analyze food nutrition |
| `/api/health` | GET | Health check |

### Example: Chat API

```bash
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Give me a high-protein vegetarian breakfast",
    "history": [],
    "familyProfiles": []
  }'
```

### Example: BMI API

```bash
curl -X POST http://localhost:5000/api/bmi \
  -H "Content-Type: application/json" \
  -d '{"weight": 70, "height": 172}'
```

---

## 🛡️ Security Notes

1. **Never commit `.env`** to git — add it to `.gitignore`
2. Set `FLASK_DEBUG=false` in production
3. Set a strong random `FLASK_SECRET_KEY`
4. Use HTTPS in production (via Nginx reverse proxy or cloud provider)
5. Rotate IBM API keys periodically

---

## 🧪 Available Granite Models

| Model ID | Best For |
|---|---|
| `ibm/granite-13b-chat-v2` | Conversational chat (recommended) |
| `ibm/granite-3-8b-instruct` | Instruction following, faster |
| `ibm/granite-8b-code-instruct` | Code + structured output |

---

## 📞 Support

- IBM Watsonx.ai Docs: https://dataplatform.cloud.ibm.com/docs/content/wsj/getting-started/welcome-main.html
- Granite Models: https://www.ibm.com/granite
- Flask Docs: https://flask.palletsprojects.com

---

*ArogyaAi v1.0 · Built with ❤️ using IBM Watsonx.ai + Granite*
