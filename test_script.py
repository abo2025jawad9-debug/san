import requests
import random
import time

def send_request(i):
    url_form = "https://quwatasad.com/worldcup2026"
    url_submit = "https://quwatasad.com/form-submit"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    session = requests.Session()
    
    # --- هام جداً: جلب الـ Token في كل مرة ---
    try:
        page = session.get(url_form, headers=headers)
        # البحث عن التوكن (تأكد أن الاسم هو _token)
        # إذا كان السيرفر يحتاج لـ Token جديد في كل مرة، يجب جلبه من صفحة الـ HTML هنا
    except:
        print(f"الطلبية {i+1}: فشل الاتصال.")
        return

    # البيانات
    teams = ['1', '2', '3', '4', '5'] 
    phone = random.choice(['77', '71', '73']) + "".join([str(random.randint(0, 9)) for _ in range(7)])
    
    payload = {
        '_token': session.cookies.get_dict().get('XSRF-TOKEN', ''), # محاولة سحب التوكن
        'customField_18': random.choice(teams),
        'customField_19': 'محمد لطف يحيى الزيلعي',
        'customField_20': phone,
        'customField_24': str(random.randint(1, 22))
    }
    
    response = session.post(url_submit, data=payload, headers=headers)
    
    # --- طباعة السبب الحقيقي ---
    if response.status_code == 200:
        print(f"الطلبية {i+1}: تم بنجاح! ✅")
    else:
        print(f"الطلبية {i+1}: فشل (كود {response.status_code})")
        # طباعة جزء من رد السيرفر لنعرف المشكلة (هل هي حظر؟ هل هو خطأ برمجي؟)
        print(f"السبب: {response.text[:100]}...") 

if __name__ == "__main__":
    for i in range(10):
        send_request(i)
        time.sleep(5) # زدنا وقت الانتظار لتجنب الحظر السريع
