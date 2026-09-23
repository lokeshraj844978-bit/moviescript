import streamlit as st
import yt_dlp
import os
import sqlite3
import json
from datetime import datetime, date
from groq import Groq

st.set_page_config(page_title="Video to Script Generator", page_icon="🎬", layout="centered")

GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            last_date TEXT,
            daily_scripts_used INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_or_create_user(email):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    today_str = str(date.today())
    c.execute("SELECT email, last_date, daily_scripts_used FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    
    if not user:
        c.execute("INSERT INTO users VALUES (?, ?, 0)", (email, today_str))
        conn.commit()
        user = (email, today_str, 0)
    else:
        # Naya din shuru hote hi limit apne aap reset ho jayegi
        if user[1] != today_str:
            c.execute("UPDATE users SET last_date = ?, daily_scripts_used = 0 WHERE email = ?", (today_str, email))
            conn.commit()
            user = (email, today_str, 0)
            
    conn.close()
    return user

def increment_script_count(email):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET daily_scripts_used = daily_scripts_used + 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()

# --- YOUTUBE FAST SUBTITLE FETCHER ---
@st.cache_data
def get_youtube_transcript(video_url):
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['hi', 'en'],
        'quiet': True,
        'no_warnings': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            subs = info.get('subtitles', {}) or info.get('automatic_captions', {})
            
            target_sub = None
            if 'hi' in subs:
                target_sub = subs['hi']
            elif 'en' in subs:
                target_sub = subs['en']
                
            if target_sub:
                for fmt in target_sub:
                    if fmt.get('ext') == 'json3':
                        import urllib.request
                        req = urllib.request.urlopen(fmt['url'])
                        data = json.loads(req.read().decode('utf-8'))
                        text_list = []
                        for event in data.get('events', []):
                            for seg in event.get('segs', []):
                                text_list.append(seg.get('utf8', ''))
                        return " ".join(text_list).strip()
    except:
        pass
    return None

# --- AUDIO EXTRACTION ---
def get_audio(video_url):
    ydl_opts = {
        'format': 'worstaudio/worst/ba',
        'outtmpl': 'compressed_audio.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'extractor_retries': 5, 
        'fragment_retries': 5,  
        'retries': 5,           
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'android', 'web', 'mweb'] 
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        filename = ydl.prepare_filename(info)
    return filename

# --- FRONTEND UI ---
st.title("🎬 Video to Script Generator")

if 'user_email' not in st.session_state:
    st.session_state['user_email'] = None

if not st.session_state['user_email']:
    st.subheader("Login / Sign Up")
    st.write("Daily 5 Free Scripts generate karne ke liye apna email daalein:")
    email_input = st.text_input("Apna Email ID daalein:", placeholder="example@gmail.com")
    if st.button("Continue"):
        if "@" in email_input and "." in email_input:
            st.session_state['user_email'] = email_input.strip().lower()
            st.rerun()
        else:
            st.error("Kripya sahi email address daalein!")
    st.stop()

email = st.session_state['user_email']
user_data = get_or_create_user(email)
daily_used = user_data[2]

col1, col2 = st.columns([2, 1])
with col1:
    st.write(f"Logged in: **{email}**")
with col2:
    if st.button("Logout"):
        st.session_state['user_email'] = None
        st.rerun()

if daily_used < 5:
    st.info(f"🎁 **Daily Free Quota:** Aaj aapne {daily_used}/5 scripts use ki hain. ({5 - daily_used} bachi hain)")
else:
    st.error("⚠️ **Aaj ki 5 free scripts poori ho chuki hain!** Kripya kal dobara aaiye.")

video_link = st.text_input("Video/Movie Link Paste Karein:", placeholder="https://www.youtube.com/watch?v=...")

if st.button("Generate Script 🚀"):
    if daily_used >= 5:
        st.error("Aapki aaj ki 5 scripts ki limit khatam ho chuki hai! Kal aaiye.")
    elif not video_link:
        st.warning("Pehle video ka link daalein!")
    else:
        raw_text = None
        with st.spinner("Video se poori script process ho rahi hai..."):
            raw_text = get_youtube_transcript(video_link)
            
            if not raw_text:
                audio_path = None
                try:
                    audio_path = get_audio(video_link)
                    with open(audio_path, "rb") as f:
                        transcription = client.audio.transcriptions.create(
                            file=f,
                            model="whisper-large-v3",
                            language="hi"
                        )
                    raw_text = transcription.text
                except Exception as e:
                    st.error(f"Error aaya: {e}")
                finally:
                    if audio_path and os.path.exists(audio_path):
                        try:
                            os.remove(audio_path)
                        except:
                            pass

        if raw_text:
            st.session_state['full_script'] = raw_text
            increment_script_count(email)
            st.rerun()

if 'full_script' in st.session_state:
    st.markdown("---")
    st.subheader("Final Clean Script:")
    st.text_area("Script Output", st.session_state['full_script'], height=380)
    st.download_button(
        label="📥 Download Full Script (.txt)",
        data=st.session_state['full_script'],
        file_name="script.txt",
        mime="text/plain"
    )
