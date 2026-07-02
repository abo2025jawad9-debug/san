import cloudscraper
import random
import time

def send_request(iteration):
    # استخدام cloudscraper لتجاوز حماية Cloudflare
    scraper = cloudscraper.create_scraper()
    
    url_form = "https://quwatasad.com/worldcup2026"
    url_submit = "https://quwatasad.com/form-submit"
    
    # 1. جلب الصفحة للحصول على الـ CSRF Token (ضروري جداً)
    try:
        page = scraper.get(url_form)
        # استخراج التوكن من الـ HTML (بافتراض أنه موجود في input باسم _token)
        # إذا كان السيرفر يحتاج للتوكن، سنقوم بجلبه هنا
        # ملاحظة: إذا كان السيرفر لا يطلب توكن في الفورم، يمكن الاستغناء عنه
    except Exception as e:
        print(f"خطأ في الاتصال بالصفحة: {e}")
        return

    # 2. توليد البيانات المطلوبة بدقة
    # الرقم: 9 خانات يبدأ بـ 77 أو 71 أو 73
    prefix = random.choice(['77', '71', '73'])
    phone = prefix + "".join([str(random.randint(0, 9)) for _ in range(7)])
    
    # مصفوفة الفرق (يمكنك إضافة أرقام الفرق التي تريدها هنا)
    teams_matrix = ['1', '5', '10', '15', '20', '25', '30', '35', '40', '45']
    
    payload = {
        '_token': 'YOUR_TOKEN_HERE', # إذا كان يتطلب توكن، يجب جلبه من الـ HTML
        'customField_18': random.choice(teams_matrix), # الفريق من المصفوفة
        'customField_19': 'محمد لطف يحيى الزيلعي',      # الاسم الرباعي
        'customField_20': phone,                        # الرقم (9 خانات)
        'customField_24': str(random.randint(1, 22))    # المحافظة (1-22)
    }
    
    # 3. إرسال الطلب
    response = scraper.post(url_submit, data=payload)
    
    # 4. فحص النتيجة
    if response.status_code == 200 and "تم الاشتراك" in response.text:
        print(f"الطلبية {iteration}: رقم {phone} - [تم القبول ✅]")
    else:
        print(f"الطلبية {iteration}: رقم {phone} - [فشل ❌ | الحالة: {response.status_code}]")

# تشغيل العملية 10 مرات
if __name__ == "__main__":
    for i in range(1, 11):
        send_request(i)
        time.sleep(5) # انتظار بين الطلبات لتجنب الحظر
