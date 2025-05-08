# affiliate.py
import qrcode
import os

def create_qr_code(link, path="affiliate_qr.png"):
    img = qrcode.make(link)
    img.save(path)
    return path

def get_affiliate_link():
    return "https://www.amazon.co.jp/dp/B0BLSMBY9X?tag=uranai-affi-22"
