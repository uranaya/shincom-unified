import qrcode
import os

def create_qr_code(data, path="qr_temp.png"):
    img = qrcode.make(data)
    img.save(path)
    return path

def get_affiliate_link():
    return "https://www.amazon.co.jp/?tag=yourtag-22"