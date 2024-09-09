import json
import os
import openai
from flask import Flask, request, jsonify
from threading import Thread
from queue import Queue
from PIL import Image
import io
import base64
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

# Initialize Flask app
app = Flask(__name__)

def resize_image(image, max_size=(1024, 1024)):
    """Resize the image if it exceeds the max_size, maintaining the aspect ratio."""
    if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
        image.thumbnail(max_size, Image.LANCZOS)
    return image

def encode_image_to_base64(image):
    """Encode image to base64."""
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def process_request(before_image, after_image, car_model, make_year, output_queue):
    # Resize images if necessary
    before_image = resize_image(before_image)
    after_image = resize_image(after_image)

    # Encode images to base64
    before_image_base64 = encode_image_to_base64(before_image)
    after_image_base64 = encode_image_to_base64(after_image)

    # Prepare the messages
    messages = [
        {
            "role": "system",
            "content": "You are an AI designed to estimate the penalty cost for car fixes by analyzing the differences between two images: one before and one after a trip for a part of car. You will be provided with the car model and make year. Your task is to calculate the cost of repair plus labor, providing the most realistic cost in INR. If your penalty amount is too high, we will lose a customer and if it is too low and not accurate, we will have to pay the loss from our end. Only answer if you have sufficient knowledge, else give sorry response. First identify each of the scratches in the image, don't use orientation like left or right in the parts detection as it can cause confusion. Try to see if the part is repairable and if it is too damaged, then go for replacement. Avoid hallucinations and minimize false positives. The response should be in JSON format, containing all details in the 'message' part and a 'cost' key with the estimated cost in INR. Use the parts price as per market rate of August 2024. Add labor cost correctly and recheck once before providing the final penalty amount."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Car Model: {car_model}\nMake Year: {make_year}"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{before_image_base64}"
                    }
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{after_image_base64}"
                    }
                }
            ]
        }
    ]

    # Make the API call to OpenAI
    response = openai.chat.completions.create(  
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.2,
        max_tokens=500
    )

    content = response.choices[0].message.content

    json_start_index = content.find("{")
    json_end_index = content.rfind("}") + 1
    json_content = content[json_start_index:json_end_index].strip()
    
    # Parse the JSON string into a Python dictionary
    parsed_json = json.loads(json_content)

    output_queue.put(parsed_json)

@app.route('/estimate_cost', methods=['POST'])
def estimate_cost():
    before_image_file = request.files['before_image']
    after_image_file = request.files['after_image']
    car_model = request.form['car_model']
    make_year = request.form['make_year']

    before_image = Image.open(before_image_file.stream)
    after_image = Image.open(after_image_file.stream)

    output_queue = Queue()

    # Start a thread for processing the request
    thread = Thread(target=process_request, args=(before_image, after_image, car_model, make_year, output_queue))
    thread.start()

    # Join the thread to ensure it finishes processing
    thread.join()

    result = output_queue.get()

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
