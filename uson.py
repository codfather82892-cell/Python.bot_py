import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import telebot

TOKEN = "8805056556:AAG-9qIkNsqUw2hgsgUQkoQPbLawjDhZtt4"
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "স্বাগতম! আমাকে যেকোনো একটি ছবি পাঠান, আমি সেটিকে আইফোনের লক স্ক্রিন স্টাইলে (সঠিক সময়সহ) রূপান্তর করে সরাসরি ফাইল ম্যানেজার বা গ্যালারিতে ডাউনলোড করার উপযোগী ডকুমেন্টস/ফাইল হিসেবে পাঠিয়ে দেবো।")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        bot.reply_to(message, "দয়া করে একটু অপেক্ষা করুন, আপনার ছবিটি প্রসেস করা হচ্ছে...")
        
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        input_path = "input.jpg"
        with open(input_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        output_path = create_iphone_lockscreen(input_path)
        
        with open(output_path, 'rb') as photo:
            bot.send_document(
                message.chat.id, 
                photo, 
                caption="✅ আপনার আইফোন স্টাইল ছবি তৈরি!\n\nএটি ফাইল ম্যানেজার বা গ্যালারিতে সেভ করতে ফাইলটিতে ক্লিক করে ৩ ডট (⋮) মেনু থেকে 'Save to downloads' বা 'Save to gallery' সিলেক্ট করুন।",
                visible_file_name="iPhone_Lockscreen.jpg"
            )
            
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)
        
    except Exception as e:
        bot.reply_to(message, f"দুঃখিত, একটি সমস্যা হয়েছে: {str(e)}")

def create_iphone_lockscreen(image_path):
    bg_width, bg_height = 1179, 2556
    
    img = Image.open(image_path)
    img = img.resize((bg_width, bg_height))
    
    draw = ImageDraw.Draw(img)
    current_time = datetime.now().strftime("%H:%M")
    
    try:
        font_large = ImageFont.truetype("arial.ttf", 200)
        font_small = ImageFont.truetype("arial.ttf", 50)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        
    text_color = (255, 255, 255)
    draw.text((420, 250), current_time, fill=text_color, font=font_large)
    draw.text((450, 2400), "Swipe up to unlock", fill=text_color, font=font_small)
    
    output_path = "output_iphone.jpg"
    img.save(output_path)
    return output_path

if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
