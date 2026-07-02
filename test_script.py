import cloudscraper
import random
import time

def send_request(i):
    # استخدام cloudscraper بدلاً من requests
    scraper = cloudscraper.create_scraper()
    
    url_submit = "https://quwatasad.com/form-submit"
    
    # البيانات العشوائية
    prefix = random.choice(['77', '71', '73'])
    phone = prefix + "".join([str(random.randint(0, 9)) for _ in range(7)])
    
    payload = {
        'customField_18': str(random.randint(1, 5)),
        'customField_19': 'محمد لطف يحيى الزيلعي',
        'customField_20': phone,
        'customField_24': str(random.randint(1, 22))
    }
    
    # الطلب عبر scraper
    response = scraper.post(url_submit, data=payload)
    
    if "تم الاشتراك" in response.text:
        print(f"الطلبية {i+1}: تم بنجاح! ✅")
    else:
        print(f"الطلبية {i+1}: فشل. كود الحالة: {response.status_code}")

if __name__ == "__main__":
    for i in range(10):
        send_request(i)
        time.sleep(5)
