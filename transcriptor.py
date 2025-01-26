import streamlit as st
from googletrans import Translator
from youtube_transcript_api import YouTubeTranscriptApi
from gtts import gTTS
from elevenlabs import generate, set_api_key, voices
import pyttsx3
import io
import os
import tempfile
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
ELEVEN_LABS_API_KEY = os.getenv('ELEVEN_LABS_API_KEY')

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    if "v=" in url:
        return url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    return url

def get_available_transcripts(video_id):
    """Get list of available transcript languages"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        return transcript_list
    except Exception as e:
        st.error(f"Error getting available transcripts: {str(e)}")
        return None

def get_transcript(video_id, target_lang='en'):
    """Get transcript and translate if needed"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available_transcript = None
        # print("Available transcripts:")
        # print(transcript_list.find_transcript(["en-IN"]))

        try:
            available_transcript = transcript_list.find_manually_created_transcript([target_lang])
        except:
            try:
                generated_transcripts = [t for t in transcript_list._manually_created_transcripts.values()]
                if not generated_transcripts:
                    generated_transcripts = [t for t in transcript_list._generated_transcripts.values()]
                if generated_transcripts:
                    available_transcript = generated_transcripts[0]
            except Exception as e:
                st.error(f"Error finding generated transcripts: {str(e)}")
                return "No transcripts available"

        if available_transcript:
            transcript_data = available_transcript.fetch()
            full_transcript = ""
            for entry in transcript_data:
                if len(entry['text']) == 0:
                    print("yes its there")
                else:
                    full_transcript += entry['text'].strip()
            # full_transcript = ' '.join([entry['text'] for entry in transcript_data])


            if target_lang != available_transcript.language_code:
                translator = Translator()
                print(str(full_transcript))
                try:
                    translated = translator.translate(str(full_transcript), dest=target_lang)
                    if translated and translated.text:
                        return f"Original transcript in {available_transcript.language_code}\nTranslated to {target_lang}:\n\n{translated.text}"
                    else:
                        return "Error in translation: Translation result is empty"
                except Exception as e:
                    st.error(f"Error in translation: {str(e)}")
                    return f"Error in translation: {str(e)}"
            return full_transcript

        return "No suitable transcript found"

    except Exception as e:
        st.error(f"Error getting transcript: {str(e)}")
        return f"Error getting transcript: {str(e)}"

def init_pyttsx3():
    """Initialize pyttsx3 engine and get available voices"""
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        return engine, voices
    except Exception as e:
        st.error(f"Error initializing speech engine: {str(e)}")
        return None, None

def text_to_speech_pyttsx3(text, voice_idx, rate, volume):
    """Convert text to speech using pyttsx3"""
    try:
        engine, voices = init_pyttsx3()
        if engine and voices:
            engine.setProperty('voice', voices[voice_idx].id)
            engine.setProperty('rate', rate)
            engine.setProperty('volume', volume)

            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
                engine.save_to_file(text, fp.name)
                engine.runAndWait()

                with open(fp.name, 'rb') as audio_file:
                    audio_buffer = io.BytesIO(audio_file.read())

            os.unlink(fp.name)
            return audio_buffer
    except Exception as e:
        st.error(f"Error in pyttsx3 conversion: {str(e)}")
        return None

def text_to_speech_gtts(text, language='en', speed=False):
    """Convert text to speech using gTTS"""
    try:
        tts = gTTS(text=text, lang=language, slow=speed)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        return audio_buffer
    except Exception as e:
        st.error(f"Error in gTTS conversion: {str(e)}")
        return None

def text_to_speech_elevenlabs(text, voice_id, speed=1.0, volume=1.0):
    """Convert text to speech using ElevenLabs with speed and volume control"""
    try:
        if not ELEVEN_LABS_API_KEY:
            raise ValueError("ElevenLabs API key not found")

        set_api_key(ELEVEN_LABS_API_KEY)
        audio = generate(
            text=text,
            voice=voice_id,
            model="eleven_multilingual_v2",
        )

        if isinstance(audio, bytes):
            audio_buffer = io.BytesIO(audio)
        else:
            audio_bytes = b''.join(audio)
            audio_buffer = io.BytesIO(audio_bytes)
        return audio_buffer
    except Exception as e:
        st.error(f"Error in ElevenLabs conversion: {str(e)}")
        return None

def main():
    st.set_page_config(page_title="YouTube Video Tools", layout="wide")
    st.title("YouTube Video Tools")

    tab1, tab2 = st.tabs(["Transcript Generator", "Text to Speech"])

    # Tab 1: Transcript Generator
    with tab1:
        st.header("YouTube Video Transcriber")

        youtube_url = st.text_input("Enter YouTube Video URL:", key="youtube_url")

        languages = {
            'English': 'en',
            'Hindi': 'hi',
        }

        target_language = st.selectbox(
            "Select target language:",
            options=list(languages.keys()),
            key="transcript_lang"
        )

        if st.button("Get Transcript"):
            if youtube_url:
                with st.spinner("Processing video..."):
                    video_id = extract_video_id(youtube_url)
                    transcripts = get_available_transcripts(video_id)

                    if transcripts:
                        st.info("Available transcript languages:")
                        for transcript in transcripts._manually_created_transcripts.values():
                            st.write(f"- {transcript.language} (Manual)")
                        for transcript in transcripts._generated_transcripts.values():
                            st.write(f"- {transcript.language} (Auto-generated)")

                        selected_lang_code = languages[target_language]
                        transcript = get_transcript(video_id, selected_lang_code)

                        st.subheader("Transcript:")
                        st.text_area("Transcript", value=transcript, height=300, label_visibility="collapsed")

                        st.download_button(
                            label="Download Transcript",
                            data=transcript,
                            file_name=f"transcript_{languages[target_language]}.txt",
                            mime="text/plain"
                        )
                    else:
                        st.error("No transcripts available for this video")
            else:
                st.error("Please enter a YouTube URL")

    # Tab 2: Text to Speech
    with tab2:
        st.header("Text to Speech Converter (ElevenLabs)")

        input_text = st.text_area(
            "Enter text to convert to speech:",
            height=200,
            key="tts_input"
        )

        col1, col2 = st.columns(2)

        # Initialize variables
        selected_voice = None
        voice_options = {}
        speed = 1.0
        volume = 0.0

        with col1:
            if ELEVEN_LABS_API_KEY:
                try:
                    set_api_key(ELEVEN_LABS_API_KEY)
                    available_voices = voices()
                    voice_options = {voice.name: voice.voice_id for voice in available_voices}

                    selected_voice = st.selectbox(
                        "Select Voice:",
                        options=list(voice_options.keys()),
                        key="eleven_voice"
                    )

                    # Add speed and volume controls
                    speed = st.slider("Speed:",
                        min_value=0.5,
                        max_value=2.0,
                        value=1.0,
                        step=0.1,
                        help="Adjust the speaking rate (0.5 = slower, 2.0 = faster)")

                    volume = st.slider("Volume:",
                        min_value=-9.0,
                        max_value=9.0,
                        value=0.0,
                        step=0.5,
                        help="Adjust the volume (negative = softer, positive = louder)")

                except Exception as e:
                    st.error("Error accessing ElevenLabs API. Please check your API key.")
            else:
                st.error("ElevenLabs API key not found in .env file")

        if st.button("Convert to Speech", key="tts_button"):
            if input_text.strip():
                with st.spinner("Converting text to speech..."):
                    if ELEVEN_LABS_API_KEY and selected_voice and selected_voice in voice_options:
                        audio_buffer = text_to_speech_elevenlabs(
                            input_text,
                            voice_options[selected_voice],
                            speed,
                            volume
                        )

                        if audio_buffer:
                            st.audio(audio_buffer, format='audio/mp3')

                            st.download_button(
                                label="Download Audio",
                                data=audio_buffer,
                                file_name="text_to_speech.mp3",
                                mime="audio/mp3",
                                key="audio_download"
                            )
                        else:
                            st.error("Failed to convert text to speech")
                    else:
                        st.error("ElevenLabs API key not found or voice not selected")
            else:
                st.error("Please enter some text to convert")

if __name__ == "__main__":
    main()
