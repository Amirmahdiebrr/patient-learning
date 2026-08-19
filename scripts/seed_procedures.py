# scripts/seed_procedures.py
"""
scripts/seed_procedures.py

Idempotent seed script for the master Procedure catalog, scoped per
StandardDepartmentType (matches scripts/seed_department_types.py
codes). Creating these rows does not require any lesson to exist yet
- procedures with no content simply won't surface anything to
patients until an admin creates procedure-specific EducationSections
for them (see content_targeting_service.py resolution order).

Run with:
    python -m scripts.seed_procedures
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import StandardDepartmentType, Procedure
from app.schemas.content_admin import slugify
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


PROCEDURES: dict[str, list[str]] = {
    "general_surgery": [
        "آپاندکتومی", "کوله‌سیستکتومی", "ترمیم فتق اینگوینال", "ترمیم فتق نافی",
        "ترمیم فتق شکمی", "جراحی روده باریک", "جراحی روده بزرگ", "کولکتومی",
        "جراحی انسداد روده", "جراحی معده", "گاسترکتومی", "جراحی رفلاکس معده",
        "جراحی هموروئید", "جراحی فیستول مقعدی", "جراحی آبسه مقعدی", "جراحی کیسه صفرا",
        "جراحی تیروئید", "جراحی پاراتیروئید", "اسپلنکتومی", "جراحی تروما",
        "لاپاراسکوپی تشخیصی",
    ],
    "orthopedics": [
        "تعویض مفصل کامل زانو", "تعویض مفصل کامل لگن", "تعویض مفصل شانه",
        "آرتروسکوپی زانو", "آرتروسکوپی شانه", "ترمیم رباط صلیبی زانو", "ترمیم منیسک",
        "جراحی شکستگی لگن", "جراحی شکستگی ران", "جراحی شکستگی ساق",
        "جراحی شکستگی مچ پا", "جراحی شکستگی بازو", "جراحی شکستگی ساعد",
        "جراحی شکستگی مچ دست", "جراحی شکستگی انگشتان", "فیکساسیون داخلی شکستگی",
        "گچ‌گیری و اقدامات جراحی مرتبط", "جراحی ستون فقرات", "دیسک کمر", "دیسک گردن",
        "جراحی تنگی کانال نخاعی",
    ],
    "urology": [
        "TURP / تراش پروستات", "پروستاتکتومی", "سنگ‌شکنی برون‌اندامی کلیه", "PCNL",
        "یورتروسکوپی و سنگ‌شکنی", "جراحی سنگ کلیه", "جراحی سنگ حالب", "جراحی سنگ مثانه",
        "نفروکتومی", "جراحی تومور کلیه", "جراحی مثانه", "TURBT",
        "ترمیم تنگی مجرای ادرار", "هیدروسل", "واریکوسل", "ختنه",
    ],
    "gynecology_surgery": [
        "سزارین", "هیسترکتومی", "میومکتومی", "جراحی کیست تخمدان", "جراحی توده تخمدان",
        "لاپاراسکوپی زنان", "هیستروسکوپی", "کورتاژ تشخیصی / درمانی",
        "جراحی حاملگی خارج رحمی", "جراحی افتادگی رحم", "ترمیم پرولاپس",
        "ترمیم آسیب‌های کف لگن",
    ],
    "ent": [
        "تونسیلکتومی", "آدنوئیدکتومی", "تونسیلوآدنوئیدکتومی", "سپتوپلاستی",
        "توربینکتومی / جراحی شاخک بینی", "FESS / جراحی آندوسکوپیک سینوس",
        "پولیپکتومی بینی", "جراحی انحراف بینی", "رینوپلاستی", "جراحی گوش میانی",
        "تمپانوپلاستی", "ماستوئیدکتومی", "جراحی پرده گوش",
    ],
    "ophthalmology": [
        "جراحی آب مروارید", "فیکوامولسیفیکاسیون", "جراحی آب سیاه", "ترابکولکتومی",
        "جراحی شبکیه", "ویترکتومی", "ترمیم پارگی شبکیه", "جراحی قرنیه", "پیوند قرنیه",
        "جراحی ناخنک", "جراحی پلک", "بلفاروپلاستی", "جراحی مجرای اشکی",
    ],
    "neurosurgery": [
        "کرانیوتومی", "برداشت تومور مغزی", "جراحی تومورهای مغزی", "تخلیه هماتوم مغزی",
        "جراحی خونریزی داخل جمجمه", "جراحی آنوریسم مغزی", "جراحی AVM", "شنت مغزی",
        "VP Shunt", "جراحی هیدروسفالی", "دیسک گردن", "دیسک کمر", "لامینکتومی",
        "جراحی تنگی کانال نخاعی", "فیوژن ستون فقرات", "جراحی شکستگی ستون فقرات",
    ],
    "cardiac_surgery": [
        "CABG / جراحی بای‌پس عروق کرونر", "تعویض دریچه قلب", "ترمیم دریچه قلب",
        "جراحی دریچه میترال", "جراحی دریچه آئورت", "جراحی آئورت", "ترمیم آنوریسم آئورت",
        "جراحی عروق محیطی", "بای‌پس عروق اندام", "جراحی واریس", "ترمیم عروق",
        "ایجاد فیستول شریانی وریدی", "جراحی شریان کاروتید",
    ],
    "plastic_surgery": [
        "ترمیم سوختگی", "گرافت پوستی", "پیوند پوست", "فلپ پوستی", "ترمیم زخم پیچیده",
        "ترمیم آسیب‌های بافت نرم", "ترمیم اسکار", "بازسازی پستان", "ماموپلاستی",
        "کوچک کردن پستان", "لیفت پستان", "بازسازی پس از تروما", "ترمیم نقص‌های مادرزادی",
        "جراحی ترمیمی دست",
    ],
    "maxillofacial_surgery": [
        "جراحی شکستگی فک", "جراحی شکستگی استخوان صورت", "جراحی شکستگی بینی",
        "جراحی فک بالا", "جراحی فک پایین", "جراحی ارتوگناتیک", "جراحی دندان نهفته",
        "جراحی کیست فک", "جراحی تومورهای فک و صورت", "ترمیم آسیب‌های بافت نرم صورت",
        "جراحی مفصل فکی‌ـ‌گیجگاهی",
    ],
}


def main():
    db = SessionLocal()
    try:
        total = 0
        for department_code, names in PROCEDURES.items():
            dept_type = db.query(StandardDepartmentType).filter(
                StandardDepartmentType.code == department_code
            ).first()
            if not dept_type:
                logger.warning(f"[Seed] department type '{department_code}' not found - skipped its procedures.")
                continue

            for order, name in enumerate(names, start=1):
                slug = slugify(name)
                existing = db.query(Procedure).filter(
                    Procedure.department_type_id == dept_type.id, Procedure.slug == slug,
                ).first()
                if existing:
                    existing.name = name
                    existing.display_order = order
                else:
                    db.add(Procedure(
                        department_type_id=dept_type.id, name=name, slug=slug, display_order=order,
                    ))
                total += 1

        db.commit()
        logger.info(f"[Seed] procedures: {total} row(s) upserted")
    finally:
        db.close()


if __name__ == "__main__":
    main()