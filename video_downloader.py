from flask import Flask, render_template, request, redirect, url_for
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

def get_video_link(querytext):
    pexel = Pexels('****************************************8')
    video_list = pexel.search_videos(query=querytext, orientation='', size='', color='', locale='', page=1, per_page=15)
    video_list
    df =pd.DataFrame.from_dict(video_list["videos"])
    # df=pd.DataFrame.from_dict(df["video_files"])
    # df=pd.DataFrame.from_dict(df["link"])
    
    id_list=df[["id","duration","video_files","image"]]
    selected_list=[]
    for index, row in id_list.iterrows():
      if row["duration"]>30:
        selected_list.append([row["id"],row["video_files"]])
    
    return selected_list[0][1][0]["link"]
def download_video(querytext):
    url=get_video_link(querytext)
    file_path="static/video.mp4"
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(file_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                file.write(chunk)
        print('Video downloaded successfully.')
    else:
        print('Failed to download video.')
    downloadingvideo=True
def text_to_speech(text, output_filename, aws_access_key_id, aws_secret_access_key):
    polly_client = boto3.Session(
                    aws_access_key_id=aws_access_key_id,
                    aws_secret_access_key=aws_secret_access_key,
                    region_name='us-west-1').client('polly')

    response = polly_client.synthesize_speech(VoiceId='Joanna',
                                              OutputFormat='mp3',
                                              Text=text)

    file = open(output_filename, 'wb')
    file.write(response['AudioStream'].read())
    file.close()

    # Request speech marks
    speechmark_response = polly_client.synthesize_speech(VoiceId='Joanna',
                                                         OutputFormat='json',
                                                         Text=text,
                                                         SpeechMarkTypes=['word'])

    # Parse speech marks
    with speechmark_response['AudioStream'] as stream:
        speechmark_data = stream.read().decode('utf-8')
    speechmarks = [json.loads(line) for line in speechmark_data.strip().split("\n")]

    # Open output file for subtitles
    with open(output_filename.replace(".mp3", ".srt"), "w") as out_file:
        index = 1
        for speechmark in speechmarks:
            if speechmark['type'] == 'word':
                # Write subtitle index
                out_file.write(str(index))
                out_file.write("\n")
                index += 1

                # Write time range
                start_time = datetime.timedelta(milliseconds=speechmark['time'])
                end_time = start_time + datetime.timedelta(milliseconds=speechmark['end'])
                out_file.write(str(start_time)[:-3] + " --> " + str(end_time)[:-3])
                out_file.write("\n")

                # Write subtitle text
                out_file.write(speechmark['value'])
                out_file.write("\n\n")
def combine_audio_video(bg_video_file, bg_audio_file, speech_audio_file, output_file, aspect_ratio='9:16'):
    # load video clip
    video = VideoFileClip(bg_video_file)
    
    # load background audio clip and adjust its duration to match speech audio's duration
    bg_audio = AudioFileClip(bg_audio_file).fx(afx.volumex, 0.2)
    
    # load speech audio clip
    speech_audio = AudioFileClip(speech_audio_file)

    # loop video until it matches the speech audio's duration
    video = video.fx(vfx.loop, duration=speech_audio.duration)
    
    # adjust background audio's duration to match video's (new) duration
    bg_audio = bg_audio.fx(vfx.loop, duration=video.duration)

    # Resize video according to aspect ratio
    if aspect_ratio == '16:9':
        video = video.fx(vfx.resize, width=video.size[1]*16/9) if video.size[0]/video.size[1] < 16/9 else video.fx(vfx.resize, height=video.size[0]*9/16)
    elif aspect_ratio == '9:16':
        video = video.fx(vfx.resize, width=video.size[1]*9/16) if video.size[0]/video.size[1] > 9/16 else video.fx(vfx.resize, height=video.size[0]*16/9)

    # Combine background audio and speech audio
    combined_audio = CompositeAudioClip([bg_audio, speech_audio])

    # set audio of video to combined audio
    final_clip = video.set_audio(combined_audio)
    rendringvideo=True
    # write to file
    final_clip.write_videofile(output_file, codec='libx264')

    return final_clip
def time_to_seconds(time_obj):
    return time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds + time_obj.milliseconds / 1000
def create_subtitle_clips(subtitles, videosize, fontsize=70, font='Futura', color='yellow', debug = False):
    subtitle_clips = []

    for subtitle in subtitles:
        start_time = time_to_seconds(subtitle.start)
        end_time = time_to_seconds(subtitle.end)
        duration = end_time - start_time

        video_width, video_height = videosize
        
        text_clip = TextClip(subtitle.text, fontsize=fontsize, font=font, color=color,stroke_color='orange', stroke_width=3,size=(video_width*3/4, None), method='caption').set_start(start_time).set_duration(duration)
        subtitle_x_position = 'center'
        subtitle_y_position = video_height*0.5

        text_position = (subtitle_x_position, subtitle_y_position)                    
        subtitle_clips.append(text_clip.set_position(text_position))

    return subtitle_clips
def subtitless(input_srt_file, output_srt_file_path, duration_sec=2):
    subs = pysrt.open(input_srt_file, encoding='iso-8859-1')
    grouped_subtitles = []
    start_time_seconds = subs[0].start.ordinal / 1000  # Initialize the start time

    # Group the words into sentences and calculate their duration
    i = 0
    while i < len(subs):
        words = []
        end_time_seconds = start_time_seconds + duration_sec
        while i < len(subs) and subs[i].start.ordinal / 1000 <= end_time_seconds:
            words.append(subs[i].text)
            i += 1

        # Create the new subtitle
        new_subtitle = pysrt.SubRipItem()
        new_subtitle.index = len(grouped_subtitles) + 1
        new_subtitle.start = pysrt.SubRipTime(0, 0, int(start_time_seconds))
        new_subtitle.end = pysrt.SubRipTime(0, 0, int(end_time_seconds))
        new_subtitle.text = ' '.join(words)
        grouped_subtitles.append(new_subtitle)

        # Update the start time for the next group of words
        start_time_seconds = end_time_seconds

    # Save the new subtitles
    grouped_file = pysrt.SubRipFile(items=grouped_subtitles)
    grouped_file.save(output_srt_file_path, encoding='utf-8')
def generate_subtitles(input_audio_file, output_srt_file, src_language="en"):

    try:
        # Generate subtitles using autosub
        command = f"autosub -S {src_language} -o {output_srt_file} {input_audio_file}"
        subprocess.check_output(command, shell=True)
        print(f"Subtitles have been generated and saved to {output_srt_file}.")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while generating subtitles: {str(e.output)}")
def render_video():
    generate_subtitles("static/voice.mp3", "static/voice.srt")
    combine_audio_video('static/video.mp4','static/bg_audio.mp3', 'static/voice.mp3',  'static/output.mp4',aspect_ratio='16:9')
    subtitless('static/voice.srt','static/final_subtittle.srt',duration_sec=2)
    srtfilename =  'static/final_subtittle.srt'
    mp4filename =  'static/output.mp4'
    video = VideoFileClip(mp4filename)
    subtitles = pysrt.open(srtfilename, encoding='iso-8859-1')
    
    video = VideoFileClip(mp4filename)
    subtitles = pysrt.open(srtfilename, encoding='iso-8859-1')

    begin,end= mp4filename.split(".mp4")
    output_video_file = begin+'_subtitled'+".mp4"

    print ("Output file name: ",output_video_file)

    # Create subtitle clips
    subtitle_clips = create_subtitle_clips(subtitles,video.size)

    # Add subtitles to the video
    final_video = CompositeVideoClip([video] + subtitle_clips)

    # Write output video file
    final_video.write_videofile(output_video_file)