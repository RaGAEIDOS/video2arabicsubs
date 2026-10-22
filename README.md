# 🎬 Video2ArabicSubs v0.2

<p align="center">
  <img src="img/first-logo-design.png" width="550" alt="Logo"/>
</p>

<p align="center">
  <strong>تحويل مقاطع الفيديو إلى ترجمة عربية (SRT / VTT) بسهولة — تطبيق سطح مكتب + تطبيق ويب</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python"/>
  <img src="https://img.shields.io/badge/version-0.2-green?logo=git"/>
  <img src="https://img.shields.io/badge/license-MIT-yellow?logo=open-source-initiative"/>
  <img src="https://img.shields.io/badge/FastAPI-0.110%2B-009688?logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey?logo=linux"/>
  <img src="https://img.shields.io/badge/whisper-small-orange?logo=openai"/>
</p>

---

## ✨ المميزات

**🖥️ تطبيق سطح المكتب (Tkinter)**

- ✅ واجهة عربية سهلة + علبة النظام (System Tray)
- ✅ معالجة عدة فيديوهات دفعة واحدة مع ترتيب ▲▼
- ✅ شريط تقدم + سجل تشغيل بالتفصيل

**🌐 تطبيق الويب (FastAPI) — جديد**

- ✅ رفع بالسحب والإفلات (Drag & Drop) مع التحقق من النوع والحجم
- ✅ استقبال روابط الفيديو (اختياري عبر `yt-dlp`)
- ✅ **تقدم لحظي عبر SSE**: استخراج الصوت ← تحويل الكلام ← الترجمة ← إنشاء الملف (نسبة + مرحلة + سجل)
- ✅ **محرر ترجمة تفاعلي** داخل المتصفح: تعديل النصوص والتوقيتات مع حفظ فوري
- ✅ **مشغل فيديو** يعرض الترجمة العربية مباشرة (`dir="rtl"` + خط Cairo/Noto Sans Arabic)
- ✅ تحميل `SRT` / `VTT` بترميز **UTF-8** (مع خيار BOM لتوافق Windows)
- ✅ **حرق الترجمة** داخل نسخة من الفيديو عبر FFmpeg (اختياري)
- ✅ **⬆ رفع النتائج إلى GitHub** بضغطة واحدة — كل الملفات في **التزام واحد** عبر Git Data API، والرمز لا يغادر جهازك
- ✅ **ترجمة صامدة أمام تقييد Google**: طلبات مدموجة (٤٠ سطراً/طلب) + حدّ سرعة + إعادة محاولة بانتظار تصاعدي، و**زر إعادة المحاولة** يستأنف من آخر نقطة محفوظة دون إعادة التحويل
- ✅ واجهة ثنائية اللغة **عربي / English** مع دعم RTL/LTR كامل
- ✅ تنظيف تلقائي للملفات المؤقتة (الفيديو المرفوع + الصوت المستخرج)

**⚙️ محرك المعالجة المشترك (`core/`)**

- ✅ محرك مستقل تماماً عن الواجهات — يخدم سطح المكتب والويب معاً
- ✅ اختيار حجم نموذج Whisper + لغة المصدر (مع اكتشاف تلقائي)
- ✅ محركات ترجمة قابلة للتوسع: Google (افتراضي) أو بدون ترجمة (فيديو عربي)
- ✅ تقدم دقيق داخل مرحلة التحويل + إمكانية الإلغاء أثناء التشغيل

---

## 📸 لقطة شاشة

<p align="center">
  <img src="screenshots/screenshots-1.png" width="700" alt="Screenshot"/>
  <img src="screenshots/Screenshot%202026-06-02%20023007.png" width="700" alt="Screenshot"/>
</p>

---

## 🚀 طريقة التشغيل

### المتطلبات الأساسية
- **Python 3.10+**
- **FFmpeg** (يُثبَّت تلقائياً عبر `imageio-ffmpeg`، ويمكن استخدام نسخة النظام)
- **اتصال بالإنترنت** (لأول تشغيل: تحميل نموذج Whisper + ترجمة Google)

### 1. تحميل المشروع

```bash
git clone https://github.com/RaGAEIDOS/video2arabicsubs.git
cd video2arabicsubs
```

### 2. تثبيت المكتبات

```bash
pip install -r requirements.txt
```

---

### 🌐 تشغيل تطبيق الويب (موصى به)

```bash
uvicorn web.main:app --reload
```

ثم افتح المتصفح على:

```
http://127.0.0.1:8000
```

> 🪄 عند أول تشغيل سيُحمَّل نموذج Whisper تلقائياً (~461 MB لنموذج `small`) إلى ذاكرة التخزين المؤقت.

**خطوات الاستخدام:**

1. **📁 ارفع الفيديو** — سحب وإفلات أو اختيار ملف (MP4 · MKV · AVI · MOV · WebM · …)
2. **⚙️ اختر الخيارات** — حجم النموذج، لغة الفيديو، محرك الترجمة، صيغة الملف، حرق الترجمة
3. **▶ ابدأ الترجمة** — تابع المراحل والنسبة لحظياً
4. **✏️ عدّل وعاين** — صحّح النصوص والتوقيتات وشاهد النتيجة داخل المشغل
5. **⬇ حمّل** — ملف SRT/VTT (UTF-8) أو الفيديو المُحروق
6. **⬆ ارفع إلى GitHub** — (اختياري) أرسل النتائج إلى أي مستودع لديك في التزام واحد

> 💡 إذا فشلت المهمة (مثلاً: «too many requests» من Google)، اضغط **↻ إعادة المحاولة** — تُستأنَف من آخر نقطة محفوظة: النص المُستخرج لا يُعاد تحويله، والترجمات المكتملة تُستخدم كما هي، ولا يُعاد إلا ما فشل فعلاً.

**⬆ رفع النتائج إلى GitHub (اختياري):**

بعد اكتمال المعالجة تظهر بطاقة «رفع النتائج إلى GitHub»: اكتب اسم المستودع (`owner/repo`) والفرع والمجلد، حدّد الملفات (SRT / VTT / الفيديو المُحروق)، ثم اضغط الرفع. يتم التثبيت من **خادمك المحلي** مباشرة عبر Git Data API (blobs ← tree ← commit ← ref) فتصل كل الملفات في **التزام واحد**، والرمز لا يُخزَّن في المتصفح ولا يُسجَّل.

- 🔑 أنشئ رمز وصول شخصي (PAT) من [GitHub → Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) بصلاحية **Contents: Read and write**.
- 🌐 أو ثبّت الرمز في متغير البيئة ليُستخدم تلقائياً (يمكنك ترك خانة الرمز فارغة في الواجهة):

  ```bash
  export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
  uvicorn web.main:app
  ```

- ⚠️ حدّ GitHub: **100 ميجابايت** لكل ملف — الفيديو المُحروق الأكبر يُرفض برسالة واضحة.

**متغيرات البيئة (اختيارية):**

| المتغير | الافتراضي | الوصف |
|---------|-----------|--------|
| `V2A_MAX_UPLOAD_MB` | `2048` | الحد الأقصى لحجم الملف المرفوع |
| `V2A_JOB_TTL` | `1800` | ثوانٍ قبل حذف نتائج المهام المنتهية تلقائياً |
| `V2A_MAX_CONCURRENT` | `1` | عدد المهام الثقيلة التي تعمل بالتوازي |
| `V2A_DATA_DIR` | `web/data` | مجلد تخزين الملفات المؤقتة والنتائج |
| `GITHUB_TOKEN` | — | رمز GitHub (PAT) لخاصية «رفع النتائج إلى GitHub» |

**دمج روابط الفيديو (اختياري):**

```bash
pip install yt-dlp
```

> بعد التثبيت يظهر تبويب «رابط» تلقائياً في الواجهة (`POST /api/url`).

**باستخدام Docker:**

```bash
docker build -t video2arabicsubs .
docker run -p 8000:8000 -v v2a-data:/data video2arabicsubs
```

> نماذج Whisper تُخزَّن داخل فولم `/data` فتبقى بعد إعادة التشغيل.

---

### 🖥️ تشغيل تطبيق سطح المكتب (Tkinter)

```bash
python main.py
```

> 🪄 عند أول تشغيل، سيقوم البرنامج **بتثبيت جميع المكتبات تلقائياً** ثم تحميل نموذج Whisper.

1. **📁 اختيار فيديوهات** — اختر ملفات الفيديو
2. **📂 اختيار مجلد** — أو اختر مجلد كامل
3. **▲ ▼** — رتب الفيديوهات حسب الأفضلية
4. **📂 تصفح** — حدد مسار حفظ ملفات الترجمة
5. **اختيار النموذج** — Tiny (أسرع) أو Small (أدق)
6. **▶ ابدأ الترجمة** — وانطلق! 🎉

---

## 🌐 نقاط الـ API

| Method | Endpoint | الوصف |
|--------|----------|-------|
| `GET` | `/api/health` | القدرات والخيارات المتاحة |
| `POST` | `/api/upload` | رفع ملف + خيارات المعالجة → `job_id` |
| `POST` | `/api/url` | استقبال رابط فيديو (يتطلب `yt-dlp`) |
| `GET` | `/api/status/{job_id}` | لقطة JSON من حالة المهمة (بديل الاستعلام) |
| `GET` | `/api/events/{job_id}` | **بث SSE** للتقدم لحظياً |
| `GET` | `/api/subtitles/{job_id}` | الترجمات المُولَّدة (JSON) |
| `PUT` | `/api/subtitles/{job_id}` | حفظ التعديلات من المحرر |
| `GET` | `/api/download/{job_id}` | تحميل `srt` / `vtt` / الفيديو المُحروق |
| `GET` | `/api/video/{job_id}` | بث الفيديو المرفوع للمشغل (يدعم Range) |
| `POST` | `/api/github/push` | رفع نتائج المهمة إلى مستودع GitHub في **التزام واحد** |
| `POST` | `/api/cancel/{job_id}` | إيقاف مهمة قيد التشغيل |
| `POST` | `/api/job/{job_id}/retry` | إعادة تشغيل مهمة فاشلة/ملغاة مع **الاستئناف** (نص وترجمات محفوظة) |
| `DELETE` | `/api/job/{job_id}` | حذف مهمة وبياناتها فوراً |

---

## 🧪 الاختبار و التطوير

```bash
# اختبار شامل بدون حاجة لنماذج Whisper (يُحاكي مراحل الذكاء الاصطناعي)
python tests/smoke_test.py

# تشغيل خادم تجريبي بنتائج وهمية — لتطوير الواجهة بدون تحميل النماذج
python tests/demo_server.py        # → http://127.0.0.1:8477
```

---

## ⚙️ التقنيات المستخدمة

| المكتبة | المهمة |
|---------|--------|
| [openai-whisper](https://github.com/openai/whisper) | تحويل الكلام إلى نص (Speech-to-Text) |
| [deep-translator](https://github.com/nidhaloff/deep-translator) | ترجمة إنجليزي → عربي (Google) |
| [moviepy](https://github.com/Zulko/moviepy) | استخراج الصوت من الفيديو |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | تضمين FFmpeg تلقائياً |
| [FastAPI](https://fastapi.tiangolo.com/) | خادم الويب + بث SSE لحظي |
| [uvicorn](https://www.uvicorn.org/) | خادم ASGI |
| [Tailwind CSS](https://tailwindcss.com/) | تنسيق الواجهة (CDN، بدون خطوة بناء) |
| [pystray](https://github.com/moses-palmer/pystray) | أيقونة علبة النظام (سطح المكتب) |
| [Pillow](https://python-pillow.org/) | معالجة الصور والأيقونات |

---

## 🛠️ بناء نسخة محمولة (EXE)

```bash
pip install pyinstaller
pyinstaller video2arabicsubs.spec
```

سيتم إنشاء ملف التنفيذ في مجلد `dist/`.

---

## 📦 هيكل المشروع

```
video2arabicsubs/
├── main.py                         # نقطة دخول تطبيق سطح المكتب
├── requirements.txt                # المكتبات المطلوبة (ويب + سطح مكتب)
├── Dockerfile                      # صورة Docker لتطبيق الويب
├── video2arabicsubs.spec           # إعدادات PyInstaller
├── img/
│   └── first-logo-design.png       # شعار التطبيق
├── core/                           # ⭐ محرك المعالجة (مستقل عن الواجهات)
│   ├── models.py                   #    Cue / JobOptions / Stage / الأحداث
│   ├── audio.py                    #    استخراج الصوت (moviepy)
│   ├── transcribe.py               #    Whisper + تقدم لحظي + إلغاء
│   ├── translate.py                #    محركات الترجمة (Google / none)
│   ├── subtitles.py                #    SRT + WebVTT (UTF-8 / BOM)
│   └── pipeline.py                 #    خط الإنتاج الكامل + حرق الفيديو
├── web/                            # 🌐 تطبيق الويب
│   ├── main.py                     #    خادم FastAPI + كل نقاط الـ API
│   ├── jobs.py                     #    مهام الخلفية + SSE + التنظيف التلقائي
│   ├── github_push.py              #    رفع النتائج إلى GitHub (Git Data API)
│   ├── schemas.py                  #    نماذج pydantic
│   └── static/                     #    الواجهة (HTML + CSS + JS)
├── app/                            # 🖥️ تطبيق سطح المكتب (Tkinter)
│   ├── gui.py                      #    الواجهة الرسومية
│   ├── processor.py                #    جسر يربط GUI بـ core/
│   ├── dependency_checker.py       #    فحص وتثبيت المكتبات
│   └── *_shims                     #    تغليف متوافق مع الكود القديم
├── tests/
│   ├── smoke_test.py               #    اختبار شامل E2E (بدون ML)
│   └── demo_server.py              #    خادم تجريبي بنتائج وهمية
└── README.md
```

---

## 👨‍💻 المطور

- **Ragaei Muhammed**
- 🚀 Powered by [OpenCode](https://opencode.ai)

---

## 📄 الترخيص

هذا المشروع مرخص تحت **MIT License** — انظر ملف [LICENSE](LICENSE) للتفاصيل.

---

<p align="center">
  <b>Made with ❤️</b>
</p>
