import requests
import random
import time

def send_request(i):
    url_form = "https://quwatasad.com/worldcup2026"
    url_submit = "https://quwatasad.com/form-submit"
    
    # تعريف الهيدرز لتبدو كمتصفح حقيقي
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    session = requests.Session()
    # جلب الصفحة للحصول على الكوكيز والـ CSRF token
    try:
        response = session.get(url_form, headers=headers)
        # استخراج الـ token من الصفحة
        # (يفضل دائماً البحث عنه في الـ HTML إذا كان متغيراً)
    except:
        print(f"الطلبية {i+1}: فشل الاتصال بالسيرفر.")
        return

    # مصفوفة الفرق (يمكنك تعديلها)
    teams = ['1', '2', '3', '4', '5'] 
    
    # توليد بيانات عشوائية
    prefix = random.choice(['77', '71', '73'])
    phone = prefix + "".join([str(random.randint(0, 9)) for _ in range(7)])
    
    payload = {
        'customField_18': random.choice(teams),
        'customField_19': 'محمد لطف يحيى الزيلعي',
        'customField_20': phone,
        'customField_24': str(random.randint(1, 22))
    }
    
    # إرسال البيانات
    response = session.post(url_submit, data=payload, headers=headers)
    
    # ضبط الترميز لضمان قراءة اللغة العربية
    response.encoding = 'utf-8'
    
    # الجملة المحددة للتحقق
    success_msg = "تم الاشتراك بالمسابقة بنجاح. شكرا لك"
    
    if success_msg in response.text:
        print(f"الطلبية {i+1}: الرقم {phone} - [تم قبول الطلب بنجاح! ✅]")
    else:
        print(f"الطلبية {i+1}: الرقم {phone} - [فشل قبول الطلب أو خطأ غير متوقع ❌]")

if __name__ == "__main__":
    print("بدء عملية الإرسال...")
    for i in range(10):
        send_request(i)
        time.sleep(3) # تأخير 3 ثوانٍ بين كل محاولة لتجنب الحظر
