from flask import Flask, render_template, request, redirect, url_for,jsonify
import requests
import openai
import json
import pandas as pd
from pexelsapi.pexels import Pexels
from video_downloader import *
import os
import random
import datetime 
import glob
from pydub import AudioSegment
from moviepy.editor import AudioFileClip
from moviepy.audio.fx import all as afx
import boto3
from moviepy.editor import *
from moviepy.video.tools.subtitles import SubtitlesClip
import subprocess
import pysubs2
import pysrt
from pysrt import open as open_srt

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Get the input from the textbox
        input_text = request.form['input_text']
        
        # Display the loading animation
        loading = True
        
        # Make an API call
        response = make_chatgpt_request(input_text)
        print(response)
        # Hide the loading animation
        loading = False
        
        # Display the result
        result = response
        return result
    
    return render_template('index.html', loading=False)

        
def make_chatgpt_request(input_text):
   #download_video(input_text) 
   openai.api_key = "*************************************"
   context = "write a creative paragraph should be close to 120 words "
   response = openai.Completion.create(engine="text-davinci-003", prompt=context + input_text,temperature=0.9,max_tokens=170)
   aws_access_key_id='***************************************'
   aws_secret_access_key='W+***************************'
   gptpromot=True
   text_to_speech(response.choices[0].text.strip(),"static/voice.mp3",aws_access_key_id,aws_secret_access_key)
   download_video(input_text)
   render_video()
   return response.choices[0].text.strip()


if __name__ == '__main__':
    app.run(debug=True)
