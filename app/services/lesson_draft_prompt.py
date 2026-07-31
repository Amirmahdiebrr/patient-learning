"""
app/services/lesson_draft_prompt.py

Prompt used by the admin panel's "generate draft" endpoint: given a
department, a journey stage, and whether the patient has surgery,
asks the AI to draft educational content for a content_manager/admin
to review and edit before publishing. This is a DRAFT ONLY - it is
never shown to a patient directly; a human must approve it via the
normal create_lesson endpoint.
"""

LESSON_DRAFT_SYSTEM_PROMPT = """
تو دستیار تولید محتوای آموزشی برای پرستاران/مدیران محتوای پلتفرم CuraLink هستی.

وظیفه‌ی تو نوشتن پیش‌نویس یک درس آموزشی برای بیماران است که بعداً توسط
یک متخصص انسانی بازبینی و ویرایش می‌شود. این متن مستقیماً به بیمار
نمایش داده نمی‌شود مگر پس از تأیید.

اطلاعات زمینه:
- بخش بیمارستان: {department_name}
- مرحله‌ی سفر بیمار: {stage_name}
- وضعیت جراحی: {surgery_context}
{topic_hint_line}

قوانین:
- متن باید فارسی، ساده، آرام‌بخش و قابل‌فهم برای یک فرد غیرمتخصص باشد.
- هیچ دارو، دوز یا تشخیص پزشکی اختصاصی ننویس - فقط اطلاعات آموزشی عمومی
  و رویه‌ای (مثل چه چیزی همراه بیاورد، چه انتظاری داشته باشد، چه زمانی
  با پرستار تماس بگیرد).
- طول متن حدود ۱۵۰ تا ۳۰۰ کلمه باشد.
- فقط متن نهایی درس را بنویس، بدون مقدمه یا توضیح اضافه درباره‌ی خودت.
"""


def build_lesson_draft_prompt(
    department_name: str,
    stage_name: str,
    has_surgery: bool | None,
    topic_hint: str | None,
) -> str:
    if has_surgery is True:
        surgery_context = "بیمار قرار است عمل جراحی داشته باشد."
    elif has_surgery is False:
        surgery_context = "بیمار عمل جراحی ندارد (درمان غیرجراحی)."
    else:
        surgery_context = "مشخص نیست."

    topic_hint_line = f"- موضوع درخواستی: {topic_hint}" if topic_hint else ""

    return LESSON_DRAFT_SYSTEM_PROMPT.format(
        department_name=department_name,
        stage_name=stage_name,
        surgery_context=surgery_context,
        topic_hint_line=topic_hint_line,
    )