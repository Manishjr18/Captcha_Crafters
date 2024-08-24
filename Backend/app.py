from captcha.image import ImageCaptcha
import random
import string
from gtts import gTTS
from flask import Flask, request, render_template, jsonify, url_for
import time
from flask import Flask
from flask_cors import CORS
from pydub import AudioSegment
from pydub.generators import WhiteNoise

from supabase import create_client, Client
from dotenv import load_dotenv
import os
import logging
from io import BytesIO

app = Flask(__name__, static_folder='static')
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})  # Allow all origins
app.secret_key = 'your_secret_key'

# Explicitly set the path to FFmpeg
os.environ["FFMPEG_BINARY"] = "ffmpeg"
os.environ["FFPROBE_BINARY"] = "ffprobe"

# Load environment variables from a .env file
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

logging.basicConfig(level=logging.DEBUG)
# logging.debug(f"Supabase URL: {SUPABASE_URL}")
# logging.debug(f"Supabase Key: {SUPABASE_KEY[:5]}...")  # Print only the first few characters for security


# Test Connection wwith Supabase using dummy database
@app.route("/check-connection")
def check_connection():
    try:
        # Example query to test connection
        response = supabase.table('TestConnection_Captcha').select('*').limit(5).execute()
        logging.debug(f"Supabase response: {response}")

        # Check for data presence
        if response.data:
            logging.info("Connected successfully and data retrieved.")
            return jsonify({"status": "success", "message": "Connected successfully", "data": response.data})
        
        logging.warning("No data returned or error occurred.")
        return jsonify({"status": "error", "message": "Failed to fetch data or no data available."})

    except Exception as e:
        logging.error(f"Exception occurred: {str(e)}")
        return jsonify({"status": "error", "message": str(e)})

def verify_valid_authorization(authorization:str):
    token = authorization.replace("Bearer","").lstrip().rstrip()
    if token == "":
        return False
    try:
        response = supabase.rpc("check_user_exists",{"user_id": token}).execute()
        return response.data
    except Exception as e:
        return False


# TEXT CAPTCHA
def generate_text_captcha():
    # num = random.randint(100000, 999999)
    captcha_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    image = ImageCaptcha()
    tstr = time.strftime("%Y%m%d-%H%M%S")
    # image_path = f'static/images/{tstr}.png' # Save image in the static directory
    # image.write(str(num), image_path)
    # return num, tstr
    image_data = BytesIO()
    image.write(str(captcha_str), image_data)
    image_data.seek(0)
    return captcha_str, tstr, image_data

def store_captcha_image_in_supabase(image_data, filename):
    try: 
        # Upload the captcha image to the Supabase storage bucket
        bucket_name = "captcha"
        folder_name = "TextCaptcha"
        path = f"{folder_name}/{filename}.png"
        
        supabase.storage.from_(bucket_name).upload(path,  image_data.read(), {'content-type': 'image/png'})
    
        # Generate and retrieve a public URL for the image
        # public_url = supabase.storage.from_(bucket_name).get_public_url(path)
        # public_url = f"https://{SUPABASE_URL.split('//')[1]}/storage/v1/object/public/{bucket_name}/{path}"

        signed_public_url = supabase.storage.from_(bucket_name).create_signed_url(path, expires_in=3600)  # URL valid for 1 hour
        public_url = signed_public_url['signedURL']
        logging.info(f"Public URL: {public_url}")
        return public_url
    
    except Exception as e:
        logging.error(f"Exception during storage operation: {str(e)}")
        return None

def insert_captcha_record_to_db(captcha_str, image_url):
    # Insert the captcha number and image URL into the Text_Captcha table
    response = supabase.table('Text_Captcha').insert({
        "captcha_text": captcha_str,
        "captcha_url": image_url
    }).execute()
    
    if response is None:
        logging.error(f"Error inserting record: {response.json()}")
        return False
    
    logging.info("Record inserted successfully.")
    return True

@app.route("/generate-text-captcha", methods=["GET", "POST"])
def generate_text_captcha_route():
    global captcha_str1, tstr
    error = None
    success = None
    image_url = None

    authorization_header = request.headers.get("Authorization")
    if authorization_header is None or not verify_valid_authorization(authorization_header):
        return jsonify(container_html=f'<h2 style="color: red;">Error: Authorization header is required to generate any type of captcha</h2>')

    if request.method == "GET" or 'captcha_str1' not in globals():
        # captcha_str1, tstr = generate_text_captcha()
        # container_html = render_template('index.html', tstr=tstr, error=error, success=success)
        # return jsonify(container_html=container_html)
        captcha_str1, tstr, image_data = generate_text_captcha()
        image_url = store_captcha_image_in_supabase(image_data, tstr)

        if image_url:
            # Insert record into database
            if insert_captcha_record_to_db(captcha_str1, image_url):
                success = "CAPTCHA generated and stored successfully!"
            else:
                error = "Failed to store CAPTCHA record in database."
        else:
            error = "Failed to upload CAPTCHA image."

        container_html = render_template('textCaptcha.html', tstr=image_url, error=error, success=success)
        return jsonify(container_html=container_html)

    if request.method == "POST":
        ip = request.form["ip"]
        try:
            if ip == captcha_str1:
                success = "CAPTCHA passed successfully!"
                error = None
            else:
                error = "Invalid CAPTCHA. Please try again."
                success = None
                # captcha_str1, tstr = generate_text_captcha()
                captcha_str1, tstr, image_data = generate_text_captcha()
                image_url = store_captcha_image_in_supabase(image_data, tstr)
                
                if image_url:
                    insert_captcha_record_to_db(captcha_str1, image_url)
                else:
                    error = "Failed to upload CAPTCHA image."
        except:
            error = "Invalid CAPTCHA. Please try again."
            success = None
            # captcha_str1, tstr = generate_text_captcha()
            captcha_str1, tstr, image_data = generate_text_captcha()
            image_url = store_captcha_image_in_supabase(image_data, tstr)
            
            if image_url:
                insert_captcha_record_to_db(captcha_str1, image_url)
            else:
                error = "Failed to upload CAPTCHA image."

        if not image_url:
            captcha_str1, tstr, image_data = generate_text_captcha()
            image_url = store_captcha_image_in_supabase(image_data, tstr)
            if image_url:
                insert_captcha_record_to_db(captcha_str1, image_url)
            else:
                error = "Failed to upload CAPTCHA image."

        container_html = render_template('textCaptcha.html', tstr=image_url, error=error, success=success)
        return jsonify(container_html=container_html)

@app.route("/refresh-text-captcha", methods=["GET"])
def refresh_text_captcha():
    # global captcha_str1, tstr
    # captcha_str1, tstr = generate_captcha()
    # new_captcha_url = url_for('static', filename='images/' + tstr + '.png', _external=True)
    # return jsonify(new_captcha_url=new_captcha_url)
    
    # global captcha_str1, tstr
    # captcha_str1, tstr = generate_text_captcha()
    # container_html = render_template('index.html', tstr=tstr, error=None, success=None)
    # return jsonify(container_html=container_html)

    global captcha_str1, tstr
    captcha_str1, tstr, image_data = generate_text_captcha()
    image_url = store_captcha_image_in_supabase(image_data, tstr)
    
    if image_url:
        insert_captcha_record_to_db(captcha_str1, image_url)
    
    container_html = render_template('textCaptcha.html', tstr=image_url, error=None, success=None)
    return jsonify(container_html=container_html)


# IMAGE CAPTCHA
# Function to fetch image URLs from Supabase storage
# def fetch_image_urls():
#     # Define the image files for each category
#     image_captcha_categories = {
#         "animals": ["animal1", "animal2", "animal3"],
#         "buildings": ["building1", "building2", "building3"],
#         "nature": ["nature1", "nature2", "nature3"],
#     }
    
#     # Retrieve signed URLs for each image
#     for category, filenames in image_captcha_categories.items():
#         for i, filename in enumerate(filenames):
#             # Get the signed URL for each image
#             file_path = f'ImageCaptcha/{filename}'
#             # logging.info(f"\n\n\nImageCaptcha Path: {file_path}\n\n\n")
#             url_response = supabase.storage.from_('captcha').create_signed_url(file_path, 60 * 60)  # URL valid for 1 hour
#             # logging.info(f"\n\n\nUrl response: {url_response}\n\n\n")
#             image_captcha_categories[category][i] = url_response['signedURL']
    
#     # logging.info(f"\n\n\nImageCaptcha Array: {image_captcha_categories}\n\n\n")
#     return image_captcha_categories

# image_captcha_categories = fetch_image_urls()

image_captcha_categories = {
    "animals": ["https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/animal1.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9hbmltYWwxLmpwZyIsImlhdCI6MTcyMjY0MDcxNiwiZXhwIjoxNzU0MTc2NzE2fQ.hC26NiXEADDO3AQG8Ao_-1AnN4SqTd6_V87AikYvQos&t=2024-08-02T23%3A18%3A36.636Z", 
                "https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/animal2.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9hbmltYWwyLmpwZyIsImlhdCI6MTcyMjY0MDc5NCwiZXhwIjoxNzU0MTc2Nzk0fQ.-4oMSvyhsSoAon0aAyps19a63dmFnXZuv9NZ4oAS9m8&t=2024-08-02T23%3A19%3A55.099Z", 
                "https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/animal3.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9hbmltYWwzLmpwZyIsImlhdCI6MTcyMjY0MDg2MCwiZXhwIjoxNzU0MTc2ODYwfQ.42rrIaVqOgUwcG4sp8IfDdLRuMe7IoPwJJLo5M2OakM&t=2024-08-02T23%3A21%3A00.268Z"],
    "buildings": ["https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/building1.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9idWlsZGluZzEuanBnIiwiaWF0IjoxNzIyNjQwOTA1LCJleHAiOjE3NTQxNzY5MDV9.olP3YzqwoEcmjZakocaijH3p4q8iGZVATVhjVrzsseA&t=2024-08-02T23%3A21%3A45.971Z", 
                  "https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/building2.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9idWlsZGluZzIuanBnIiwiaWF0IjoxNzIyNjQwOTU4LCJleHAiOjE3NTQxNzY5NTh9.bCkF6jawUVqTmidYr1ZVVkFz8psmvpz7wLP16Chy3yk&t=2024-08-02T23%3A22%3A38.941Z", 
                  "https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/building3.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9idWlsZGluZzMuanBnIiwiaWF0IjoxNzIyNjQwOTg4LCJleHAiOjE3NTQxNzY5ODh9.t1fsgVf3DJk7TnRcAcOB89Jof7QZIlzfxJQBpyrieRY&t=2024-08-02T23%3A23%3A08.439Z"],
    "nature": ["https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/nature1.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9uYXR1cmUxLmpwZyIsImlhdCI6MTcyMjY0MTAxNiwiZXhwIjoxNzU0MTc3MDE2fQ.Zv_wjTFSdCVhdJAKd1fUiuCoxOvAhhG3zKN2Exd-CNc&t=2024-08-02T23%3A23%3A37.071Z", 
               "https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/nature2.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9uYXR1cmUyLmpwZyIsImlhdCI6MTcyMjY0MTA0NSwiZXhwIjoxNzU0MTc3MDQ1fQ.7_JyzfTYD9VMRYipEWiouh6P4yIGTcd7K2z6a7TqB8U&t=2024-08-02T23%3A24%3A05.172Z", 
               "https://zefmkybtujcymwqfbvcf.supabase.co/storage/v1/object/sign/captcha/ImageCaptcha/nature3.jpg?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJjYXB0Y2hhL0ltYWdlQ2FwdGNoYS9uYXR1cmUzLmpwZyIsImlhdCI6MTcyMjY0MTA2NywiZXhwIjoxNzU0MTc3MDY3fQ.skcc0hFTYb_CpJwez7Pu0cNodZWXvWAdZRg0d2aioI4&t=2024-08-02T23%3A24%3A27.475Z"],
}

def generate_image_captcha(sample_image_captcha_category):
    captcha_images = []
    other_categories = [img for img in image_captcha_categories.keys() if img != sample_image_captcha_category]
    
    # Add 3 random images from the sample category
    captcha_images.extend(random.sample(image_captcha_categories[sample_image_captcha_category], 3))
    
    # Add 5 random images from other categories
    for category in other_categories:
        captcha_images.extend(random.sample(image_captcha_categories[category], 2))
    
    # Add one more random image from the remaining images if the total is less than 8
    if len(captcha_images) < 8:
        remaining_images = []
        for category in other_categories:
            remaining_images.extend([img for img in image_captcha_categories[category] if img not in captcha_images])
        remaining_images.extend([img for img in image_captcha_categories[sample_image_captcha_category] if img not in captcha_images])
        captcha_images.append(random.choice(remaining_images))
    
    random.shuffle(captcha_images)
    return captcha_images[:8]

@app.route('/generate-image-captcha')
def generate_image_captcha_route():
    authorization_header = request.headers.get("Authorization")
    print("AUTH_TOKEN",authorization_header)
    if authorization_header is None or not verify_valid_authorization(authorization_header):
        print('VERIFY_TOKEN',verify_valid_authorization(authorization_header))
        return jsonify(container_html=f'<h2 style="color: red;">Error: Authorization header is required to generate any type of captcha</h2>')
    sample_image_captcha_category = random.choice(list(image_captcha_categories.keys()))
    sample_image = random.choice(image_captcha_categories[sample_image_captcha_category])
    captcha_images = generate_image_captcha(sample_image_captcha_category)

    response = {
        "image_captcha_id": sample_image_captcha_category,
        "sample_image": sample_image,
        "captcha_images": captcha_images
    }
    return jsonify(response)

@app.route('/verify-image-captcha', methods=['POST'])
def verify_image_captcha():
    data = request.get_json()
    image_captcha_id = data['image_captcha_id']
    user_selection = data['user_selection']

    correct_images = set(image_captcha_categories[image_captcha_id])
    selected_images = set(user_selection)

    if correct_images == selected_images:
        result = "Captcha Verified Successfully"
    else:
        result = "Captcha Verification Failed"

    return jsonify({"result": result})

@app.route('/render-image-captcha-template')
def index():
    authorization_header = request.headers.get("Authorization")
    if authorization_header is None or not verify_valid_authorization(authorization_header):
        return jsonify(container_img_html=f'<h2 style="color: red;">Error: Authorization header is required to generate any type of captcha</h2>')
    container_img_html = render_template('imageCaptcha.html')
    return jsonify(container_img_html=container_img_html)


# AUDIO CAPTCHA
def generate_audio(captcha_str):
    # Create the initial message
    initial_message = f"All alphabets are in upper case. The captcha is:"
    tts_initial = gTTS(text=initial_message, lang='en')
    tts_initial.save("temp_initial.mp3")
    
    # Load the initial audio
    initial_audio = AudioSegment.from_mp3("temp_initial.mp3")
    
    # Define a minimal delay between the initial message and CAPTCHA pronunciation
    delay_before_captcha = 1000  # milliseconds (1 second)

    # Create TTS segments for each character with a minimal delay
    char_delay = 300  # milliseconds
    character_segments = []
    
    for char in captcha_str:
        message = f"{char}"
        tts_char = gTTS(text=message, lang='en')
        tts_char.save(f"char_{char}.mp3")
        
        char_audio = AudioSegment.from_mp3(f"char_{char}.mp3")
        character_segments.append(char_audio)
        character_segments.append(AudioSegment.silent(duration=char_delay))  # Add minimal delay

        os.remove(f"char_{char}.mp3")

    # Combine the initial audio with a delay and character segments
    delay_audio = AudioSegment.silent(duration=delay_before_captcha)
    combined_audio = initial_audio + delay_audio
    for segment in character_segments:
        combined_audio += segment

    # Add background noise
    noise = WhiteNoise().to_audio_segment(duration=len(combined_audio))
    noise = noise - 30  # Lower the volume of the noise
    final_audio = noise.overlay(combined_audio)

    # Export the final audio
    # audio_url = f'./static/audio/{captcha_str}.mp3'
    # audio_url = store_captcha_audio_in_supabase()
    # final_audio.export(audio_url, format="mp3")
    
    os.remove("temp_initial.mp3")

    # Export the final audio to a BytesIO object
    audio_data = BytesIO()
    final_audio.export(audio_data, format="mp3")
    audio_data.seek(0)

    # Upload to Supabase and return the public URL
    audio_url = store_captcha_audio_in_supabase(audio_data, captcha_str)
    return audio_url

def store_captcha_audio_in_supabase(audio_data, filename):
    try: 
        # Upload the captcha audio to the Supabase storage bucket
        bucket_name = "captcha"
        folder_name = "AudioCaptcha"
        path = f"{folder_name}/{filename}.mp3"
        
        supabase.storage.from_(bucket_name).upload(path, audio_data.read(), {'content-type': 'audio/mpeg'})
    
        # Generate and retrieve a public URL for the image
        # public_url = supabase.storage.from_(bucket_name).get_public_url(path)
        # public_url = f"https://{SUPABASE_URL.split('//')[1]}/storage/v1/object/public/{bucket_name}/{path}"

        signed_public_url = supabase.storage.from_(bucket_name).create_signed_url(path, expires_in=3600)  # URL valid for 1 hour
        public_url = signed_public_url['signedURL']
        logging.info(f"Public URL: {public_url}")
        return public_url
    
    except Exception as e:
        logging.error(f"Exception during storage operation: {str(e)}")
        return None

def insert_audio_captcha_record_to_db(captcha_str, audio_url):
    # Insert the captcha text and image URL in the Audio_Captcha table
    response = supabase.table('Audio_Captcha').insert({
        "captcha_text": captcha_str,
        "captcha_url": audio_url
    }).execute()
    
    if response is None:
        logging.error(f"Error inserting record: {response.json()}")
        return False
    
    logging.info("Record inserted successfully.")
    return True

@app.route("/generate-audio-captcha", methods=["GET", "POST"])
def generate_audio_captcha_route():
    global captcha_str1, tstr
    error = None
    success = None

    authorization_header = request.headers.get("Authorization")
    if authorization_header is None or not verify_valid_authorization(authorization_header):
        return jsonify(container_audio_html=f'<h2 style="color: red;">Error: Authorization header is required to generate any type of captcha</h2>')

    if request.method == "GET" or 'captcha_str1' not in globals():
        captcha_str1, tstr, image_data = generate_text_captcha()
        image_url = store_captcha_image_in_supabase(image_data, tstr)

        if image_url:
            # Insert record into database
            if insert_captcha_record_to_db(captcha_str1, image_url):
                success = "CAPTCHA generated and stored successfully!"
            else:
                error = "Failed to store CAPTCHA record in database."
        else:
            error = "Failed to upload CAPTCHA image."

        audio_url = generate_audio(captcha_str1)
        if audio_url:
            # Insert audio record into database
            if insert_audio_captcha_record_to_db(captcha_str1, audio_url):
                success = "CAPTCHA audio generated and stored successfully!"
            else:
                error = "Failed to store CAPTCHA audio record in database."
        else:
            error = "Failed to upload CAPTCHA audio."

        container_audio_html = render_template('audioCaptcha.html', image_url=image_url, audio_url=audio_url, error=error, success=success)
        return jsonify(container_audio_html=container_audio_html)

    if request.method == "POST":
        ip = request.form["ip"]
        try:
            if ip == captcha_str1:
                success = "CAPTCHA passed successfully!"
                error = None
                # captcha_str1, tstr = generate_text_captcha()
                # audio_url = generate_audio(captcha_str1)
            else:
                error = "Invalid CAPTCHA. Please try again."
                success = None
                # captcha_str1, tstr = generate_text_captcha()
                # audio_url = generate_audio(captcha_str1)

            # Generate a new CAPTCHA regardless of success or failure
            captcha_str1, tstr, image_data = generate_text_captcha()
            image_url = store_captcha_image_in_supabase(image_data, tstr)
            if image_url:
                insert_captcha_record_to_db(captcha_str1, image_url)

            audio_url = generate_audio(captcha_str1)
            if audio_url:
                insert_audio_captcha_record_to_db(captcha_str1, audio_url)

        except:
            error = "Invalid CAPTCHA. Please try again."
            success = None
            # captcha_str1, tstr = generate_text_captcha()
            # audio_url = generate_audio(captcha_str1)

            # Generate a new CAPTCHA in case of exception
            captcha_str1, tstr, image_data = generate_text_captcha()
            image_url = store_captcha_image_in_supabase(image_data, tstr)
            if image_url:
                insert_captcha_record_to_db(captcha_str1, image_url)

            audio_url = generate_audio(captcha_str1)
            if audio_url:
                insert_audio_captcha_record_to_db(captcha_str1, audio_url)

        container_audio_html = render_template('audioCaptcha.html', image_url=image_url, audio_url=audio_url, error=error, success=success)
        return jsonify(container_audio_html=container_audio_html)

@app.route("/refresh-audio-captcha", methods=["GET"])
def refresh_audio_captcha():
    global captcha_str1, tstr
    success = None
    error = None
    # captcha_str1, tstr = generate_text_captcha()
    # audio_url = generate_audio(captcha_str1)
    # new_audio_captcha_url = url_for('static', filename='images/' + tstr + '.png')
    # new_audio_url = url_for('static', filename='audio/' + captcha_str1 + '.mp3')
    # return jsonify(new_audio_captcha_url=new_audio_captcha_url, new_audio_url=new_audio_url)

    authorization_header = request.headers.get("Authorization")
    if authorization_header is None or not verify_valid_authorization(authorization_header):
        return jsonify(container_audio_html=f'<h2 style="color: red;">Error: Authorization header is required to generate any type of captcha</h2>')

    captcha_str1, tstr, image_data = generate_text_captcha()
    image_url = store_captcha_image_in_supabase(image_data, tstr)
    
    if image_url:
            # Insert record into database
            if insert_captcha_record_to_db(captcha_str1, image_url):
                success = "CAPTCHA generated and stored successfully!"
            else:
                error = "Failed to store CAPTCHA record in database."
    else:
        error = "Failed to upload CAPTCHA image."

    audio_url = generate_audio(captcha_str1)
    if audio_url:
        # Insert audio record into database
        if insert_audio_captcha_record_to_db(captcha_str1, audio_url):
            success = "CAPTCHA audio generated and stored successfully!"
        else:
            error = "Failed to store CAPTCHA audio record in database."
    else:
        error = "Failed to upload CAPTCHA audio."
    
    # return jsonify(new_audio_captcha_url=image_url, new_audio_url=audio_url)
    container_audio_html = render_template('audioCaptcha.html', image_url=image_url, audio_url=audio_url, error=error, success=success)
    return jsonify(container_audio_html=container_audio_html)



# MAIN
if __name__ == "__main__":
    app.debug = True
    app.run(host="0.0.0.0", threaded=True, use_reloader=True)
