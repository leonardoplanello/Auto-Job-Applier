<div align="center">
  <img src="https://img.icons8.com/fluency/96/bot.png" alt="Logo" width="80" height="80">
  <h1 align="center">Auto Job Applier</h1>
  
  <p align="center">
    <strong>100% Local, Self-Learning Job Application Assistant</strong>
    <br />
    A powerful automation tool to streamline your job search and application process.
  </p>

  <p align="center">
    <a href="#-features">Features</a> •
    <a href="#-tech-stack">Tech Stack</a> •
    <a href="#-quick-start">Quick Start</a> •
    <a href="#-how-it-works">How It Works</a> •
    <a href="#-disclaimer">Disclaimer</a>
  </p>
</div>

---

## ✨ Features

- **🤖 Automated Applications:** Automate the tedious process of applying for jobs on platforms like LinkedIn utilizing Playwright browser automation.
- **🧠 Self-Learning:** The bot adapts and learns from your profile and QA responses to accurately fill out new application forms over time.
- **💻 100% Local & Private:** All your data (profile, job history, Q&A pairs, resumes) is stored locally in a SQLite database. No personal data is sent to external cloud servers.
- **📊 Interactive Dashboard:** A beautiful, responsive React frontend to manage your profile, view applied jobs, track application statuses, and manage bulk actions effortlessly.
- **⚡ Real-time Updates:** Watch the bot's progress in real-time through seamless WebSocket connections.

## 🛠️ Tech Stack

### Backend
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) for a lightning-fast, modern Python API.
- **Automation:** [Playwright](https://playwright.dev/python/) for robust and undetectable browser automation.
- **Database:** SQLite with [SQLAlchemy](https://www.sqlalchemy.org/) ORM.
- **Communication:** WebSockets for real-time bi-directional events.

### Frontend
- **Framework:** [React 19](https://react.dev/) + [Vite](https://vitejs.dev/).
- **Styling:** [Tailwind CSS](https://tailwindcss.com/) for beautiful, responsive design.
- **State Management:** [Zustand](https://github.com/pmndrs/zustand).
- **Icons & Charts:** Lucide React and Nivo Charts.

## 🚀 Quick Start

Getting started is incredibly easy. The project includes an automated setup script that handles all dependencies and builds the frontend for you out of the box.

### Prerequisites
- **Python 3.9+**
- **Node.js 18+** (Required for building the React frontend)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/Auto-Job-Applier.git
   cd Auto-Job-Applier
   ```

2. **Run the application:**
   ```bash
   python run.py
   ```
   
   The `run.py` script is fully automated and will:
   - Install all required Python packages from `requirements.txt`.
   - Install npm dependencies and build the React frontend.
   - Start the FastAPI backend and serve the frontend on `http://localhost:7000`.
   - Automatically open your default web browser to the dashboard.

## 💡 How It Works

1. **Set Up Your Profile:** Fill in your personal information, work experience, education, and skills in the dashboard's profile section.
2. **Search for Jobs:** Configure your job search parameters (keywords, location, specific filters).
3. **Start the Bot:** Launch the bot from the UI. It will open a browser, log in, search for relevant jobs, and begin applying.
4. **Answer Questions (Q&A):** As the bot encounters new questions in application forms, it may pause and ask for your input. Once answered, it securely saves the response for future applications.
5. **Track Progress:** Monitor the jobs you've applied to, view success/failure rates, and manage your application history right from the intuitive dashboard.

## ⚠️ Disclaimer

This tool is designed for educational purposes and personal use to save time. Automating interactions with websites may violate their Terms of Service (e.g., LinkedIn). Use this tool responsibly and entirely at your own risk. The developers are not responsible for any account bans, restrictions, or damages.

---

<div align="center">
  Made with ❤️ by the Auto Job Applier Contributors
</div>
