# 🚀 Deploying to Render (render.com)

This guide provides step-by-step instructions for deploying the **AI-Powered Ride Booking Platform** on [Render](https://render.com).

You have two deployment choices:
- **Method 1 (Recommended)**: **Render Blueprint** (Automated 2-service setup with [`render.yaml`](file:///c:/Users/Administrator/Desktop/demo_ride_booking_agent/render.yaml))
- **Method 2**: **Single Docker Web Service** (Runs both FastAPI and Next.js in 1 container via [`Dockerfile`](file:///c:/Users/Administrator/Desktop/demo_ride_booking_agent/Dockerfile))
- **Method 3**: **Manual Dashboard Setup** (Step-by-step via Render UI)

---

## Method 1: Render Blueprint (Easiest — 1 Click)

Render Blueprints use Infrastructure as Code (`render.yaml`). Render automatically detects both the FastAPI backend and Next.js frontend, wires them together, and provisions them.

### Steps:
1. **Push your code to GitHub / GitLab**:
   ```bash
   git add .
   git commit -m "Add Render deployment configuration"
   git push origin main
   ```
2. Log in to [dashboard.render.com](https://dashboard.render.com).
3. Click the **New +** button in the top navigation and select **Blueprint**.
4. Connect your GitHub/GitLab repository.
5. Render will automatically parse [`render.yaml`](file:///c:/Users/Administrator/Desktop/demo_ride_booking_agent/render.yaml) and display:
   - **`ride-booking-backend`** (Python Web Service)
   - **`ride-booking-frontend`** (Node.js Web Service)
6. Under **Environment Variables**, fill in your API keys (or leave blank if using deterministic fallback mode):
   - `OPENAI_API_KEY` *(Optional: Enables GPT-4o-mini tool loop)*
   - `GROQ_API_KEY` *(Optional: Enables Groq Whisper STT)*
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` *(Optional: Live telephony)*
7. Click **Apply**.
8. Render will build and deploy both services!

---

## Method 2: Single All-in-One Docker Web Service (Saves Free Tier Slots)

If you prefer to deploy everything under a single Render Web Service URL:

### Steps:
1. Push your repository to GitHub.
2. In the Render Dashboard, click **New +** -> **Web Service**.
3. Select your repository.
4. Configure the service:
   - **Name**: `ride-booking-app`
   - **Language / Runtime**: **Docker**
   - **Region**: Any (e.g. *Oregon* or *Frankfurt*)
   - **Instance Type**: **Free**
5. Add Environment Variables (under **Environment** tab):
   - `OPENAI_API_KEY`: your OpenAI key (optional)
   - `GROQ_API_KEY`: your Groq key (optional)
   - `TWILIO_ACCOUNT_SID`: (optional)
   - `TWILIO_AUTH_TOKEN`: (optional)
   - `TWILIO_PHONE_NUMBER`: (optional)
6. Click **Deploy Web Service**.
7. Render will build the Docker container and start both the FastAPI backend and Next.js frontend on port `$PORT`.

---

## Method 3: Manual Render Setup (Step-by-Step UI)

If configuring services manually without Blueprints:

### Step 3A: Create the Backend Service
1. In Render Dashboard, click **New +** -> **Web Service**.
2. Connect your repo and configure:
   - **Name**: `ride-booking-backend`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables**:
     - `PYTHON_VERSION`: `3.11.9`
     - `DEBUG`: `false`
     - `DATABASE_URL`: `sqlite:///./ride_booking.db`
3. Click **Create Web Service**. Note your backend URL (e.g. `https://ride-booking-backend.onrender.com`).

### Step 3B: Create the Frontend Service
1. Click **New +** -> **Web Service**.
2. Connect your repo and configure:
   - **Name**: `ride-booking-frontend`
   - **Runtime**: `Node`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Start Command**: `npm run start`
   - **Environment Variables**:
     - `NODE_VERSION`: `20.14.0`
     - `BACKEND_URL`: `https://ride-booking-backend.onrender.com` (use your backend URL from Step 3A)
3. Click **Create Web Service**.

---

## Post-Deployment Verification

1. **Check Backend**:
   Visit `https://<your-backend-url>/` or `https://<your-backend-url>/docs`.
   You should see:
   ```json
   {
     "status": "healthy",
     "service": "AI-Powered Ride Booking Platform",
     "docs_url": "/docs"
   }
   ```
2. **Check Frontend**:
   Visit `https://<your-frontend-url>/`.
   The dashboard should load with the **Active Driver Fleet (24)**, **Live Ride Dispatch Board**, and the **Interactive Channel Simulator**.
3. **Configure Twilio Webhook (Optional for Live Phone Calls & SMS)**:
   In your Twilio Console, point your phone number's webhooks to:
   - **Voice Webhook**: `https://<your-backend-url>/voice/inbound` (HTTP POST)
   - **Messaging Webhook**: `https://<your-backend-url>/sms/incoming` (HTTP POST)
