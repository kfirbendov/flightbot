# בוט מעקב מחירי טיסות - תל אביב ↔ בנגקוק (אל על, ישירה)

בודק כל 20 דקות את המחירים לתאריכים 7-10 בספטמבר 2026, ושולח לך הודעת
**טלגרם** ברגע שהמחיר יורד מתחת ל-₪2,000.

⚠️ זו גרידת מידע (scraping) מגוגל פלייטס - לשימוש אישי בלבד. אם גוגל משנה
את מבנה הדף בעתיד, יכול להיות שהבוט יפסיק למצוא מחירים - תגידו לי ואני אתקן.

---

## הדרך הפשוטה: GitHub Actions (בלי מחשב דלוק, בלי טרמינל)

זה רץ על השרתים של GitHub בחינם, לפי לוח זמנים - אתה לא צריך להשאיר כלום
פתוח. ההגדרה היא רק דרך אתר, בלי שורת פקודה.

### שלב 1: צור חשבון GitHub (אם אין לך)
לך ל-https://github.com/signup - חינמי.

### שלב 2: צור ריפוזיטורי חדש
1. לחץ על ה-**+** למעלה מימין → **New repository**
2. תן שם (למשל `flight-price-bot`)
3. בחר **Private** (כדי שאף אחד אחר לא יראה את זה)
4. לחץ **Create repository**

### שלב 3: העלה את הקבצים
1. בדף הריפו החדש, לחץ **Add file → Upload files**
2. גרור לשם את **כל** התיקייה שקיבלת ממני (כולל התיקייה `.github` עם
   תת-התיקייה `workflows` בפנים, והתיקייה `data`) - שמור על אותו מבנה תיקיות
3. לחץ **Commit changes**

> טיפ: אם הדפדפן לא נותן לך לגרור תיקיות עם תתי-תיקיות (`.github/workflows/`),
> תוכל ליצור את הקבצים ידנית באתר: **Add file → Create new file**, ובשם
> הקובץ הקלד את הנתיב המלא כמו `.github/workflows/check_price.yml` -
> GitHub ייצור את התיקיות אוטומטית.

### שלב 4: צור בוט טלגרם (2 דקות)
1. בטלגרם, חפש **@BotFather** → שלח `/newbot` → עקוב אחרי ההוראות → תקבל **טוקן**
2. שלח כל הודעה לבוט החדש שיצרת (כדי שיהיה לו ממי לקבל הודעות)
3. פתח בדפדפן: `https://api.telegram.org/bot<הטוקן שלך>/getUpdates`
4. חפש שם `"chat":{"id": 123456789}` - זה ה-**chat ID** שלך

### שלב 5: הכנס את הפרטים כ-Secrets (סודות) בגיטהאב
1. בריפו שיצרת: **Settings → Secrets and variables → Actions**
2. לחץ **New repository secret**, צור שני סודות:
   - שם: `TELEGRAM_BOT_TOKEN` | ערך: הטוקן מ-BotFather
   - שם: `TELEGRAM_CHAT_ID` | ערך: ה-chat ID שמצאת
3. זהו - הפרטים שלך שמורים בצורה מוצפנת, לא גלויים לאף אחד

### שלב 6: בדיקה שזה עובד
1. לך לטאב **Actions** בריפו
2. תראה שם workflow בשם **Flight Price Check**
3. לחץ עליו → **Run workflow** → **Run workflow** (הרצה ידנית לבדיקה)
4. אחרי דקה-שתיים לחץ על ההרצה שרצה כדי לראות את הלוג - אמור להראות את
   המחיר שנמצא לכל תאריך

מפה זה רץ **לבד, אוטומטית, כל 20 דקות**, בלי שתצטרך לגעת בכלום. אם מחיר
יורד מתחת ל-₪2,000 - תקבל הודעה בטלגרם עם התאריך והקישור.

---

## שינוי הסף / הטווח / הטיסה

כל ההגדרות נמצאות בקובץ `.github/workflows/check_price.yml`, בחלק
שנקרא `env:`. פשוט ערכו את הערכים שם ישירות באתר (Edit ✏️ על הקובץ בגיטהאב):

- `PRICE_THRESHOLD_NIS` - הסף בשקלים
- `START_DATE` / `END_DATE` - טווח תאריכים (פורמט `YYYY-MM-DD`)
- `ORIGIN` / `DESTINATION` / `AIRLINE` - מסלול אחר

אחרי שמירת השינוי, ההרצה הבאה (עד 20 דקות) תשתמש בהגדרות החדשות.

---

## היסטוריית מחירים

כל בדיקה נשמרת ל-`data/price_history.csv` בתוך הריפו - אפשר לפתוח את
הקובץ הזה בגיטהאב בכל רגע ולראות איך המחיר זז לאורך זמן לכל תאריך.

---

## אם משהו לא עובד

לך לטאב **Actions** בריפו → לחץ על ההרצה האחרונה שנכשלה (סימן ❌ אדום) →
תראה שם את הלוג המדויק של השגיאה. הסיבות הכי נפוצות:
1. שם ה-Secret לא בדיוק `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` (רגיש לאותיות גדולות/קטנות)
2. לא שלחת הודעה לבוט לפני שמשכת את ה-chat ID
3. גוגל שינה את מבנה העמוד - תגידו לי ואני אעדכן את קוד הזיהוי

---

## חלופה: הרצה מהמחשב שלך (למי שנוח עם טרמינל)

אם אתה כן רוצה להריץ מקומית עם `cron` / Task Scheduler במקום GitHub
Actions, ההוראות המלאות נמצאות למטה.

### התקנה

```bash
cd flight_bot
python3 -m venv venv
source venv/bin/activate          # ב-Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### קונפיגורציה

```bash
cp .env.example .env
```
ערוך את `.env` ומלא `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (ראה שלב 4
למעלה ליצירת הבוט).

### הרצה ידנית

```bash
source venv/bin/activate
export $(cat .env | xargs)
python3 flight_price_monitor.py
```

### הרצה אוטומטית (macOS/Linux עם cron)

```bash
crontab -e
```
```
*/20 * * * * cd /full/path/to/flight_bot && export $(cat .env | xargs) && venv/bin/python3 flight_price_monitor.py >> data/cron.log 2>&1
```

### הרצה אוטומטית (Windows עם Task Scheduler)

Task Scheduler → Create Task → Trigger: repeat every 20 min → Action:
`venv\Scripts\python.exe flight_price_monitor.py` עם "Start in" מוגדר
לתיקיית הפרויקט.
