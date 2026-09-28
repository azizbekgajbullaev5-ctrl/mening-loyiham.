"""Ikki tilli (o'zbek / rus) interfeys matnlari."""

LANGUAGES = {
    "uz": "🇺🇿 O'zbekcha",
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 English",
}

TEXTS = {
    "uz": {
        "choose_language": "Тилни танланг / Выберите язык:",
        "welcome": (
            "👋 Ассалому алейкум!\n\n"
            "Мен <b>ОАК талаблари асосида илмий мақола</b> ёзиб берадиган ботман.\n\n"
            "Мақола қуйидаги тузилишда тайёрланади:\n"
            "• УДК\n"
            "• Сарлавҳа\n"
            "• Аннотация ва калит сўзлар (ўзбек, рус, инглиз)\n"
            "• Кириш\n"
            "• Асосий қисм (таҳлил ва усуллар)\n"
            "• Натижалар ва уларнинг таҳлили\n"
            "• Хулоса\n"
            "• Фойдаланилган адабиётлар рўйхати\n\n"
            "Бошлаш учун /new буйруғини юборинг."
        ),
        "menu_new": "📝 Янги мақола ёзиш — /new",
        "menu_lang": "🌐 Тилни ўзгартириш — /lang",
        "menu_help": "ℹ️ Ёрдам — /help",
        "ask_topic": (
            "📌 <b>1/4</b> Мақола мавзусини киритинг.\n\n"
            "Масалан: <i>«Рақамли иқтисодиёт шароитида кичик бизнесни ривожлантириш»</i>"
        ),
        "ask_field": (
            "🔬 <b>2/4</b> Илмий соҳани (йўналишни) киритинг.\n\n"
            "Масалан: <i>иқтисодиёт, педагогика, ахборот технологиялари, тиббиёт...</i>"
        ),
        "ask_author": (
            "✍️ <b>3/4</b> Муаллиф маълумотларини киритинг "
            "(Ф.И.Ш., лавозим, муассаса).\n\n"
            "Масалан: <i>Каримов А.А., таянч докторант, ТДИУ</i>\n\n"
            "Агар кераксиз бўлса <b>—</b> белгисини юборинг."
        ),
        "ask_keywords": (
            "🏷 <b>4/5</b> Калит сўзларни киритинг (вергул билан ажратиб).\n\n"
            "Агар ботнинг ўзи танласин десангиз <b>—</b> белгисини юборинг."
        ),
        "ask_pages": (
            "📄 <b>5/5</b> Мақола неча бет бўлсин?\n\n"
            "{min} дан {max} гача рақам киритинг."
        ),
        "choose_kind": (
            "🧩 Мақола турини танланг ({pages} бет):\n\n"
            "📄 <b>Оддий</b> — матн, аннотация ва адабиётлар.\n"
            "    Нархи: <b>{std} сўм</b>\n\n"
            "📊 <b>Premium</b> — жадвал ва диаграммалар билан.\n"
            "    Нархи: <b>{prem} сўм</b>"
        ),
        "btn_kind_standard": "📄 Оддий",
        "btn_kind_premium": "📊 Premium (жадвал+диаграмма)",
        "invalid_pages": (
            "⚠️ Илтимос, {min} дан {max} гача бутун рақам киритинг."
        ),
        "payment_info": (
            "💳 <b>Тўлов</b>\n\n"
            "Мақола ҳажми: <b>{pages} бет</b>\n"
            "Жами тўлов: <b>{total} сўм</b>\n\n"
            "Қуйидаги пластик картага тўлов қилинг:\n"
            "💳 <code>{card}</code>\n"
            "👤 {holder}\n\n"
            "Тўлов қилгач, <b>тўлов чекини (скриншот/расм)</b> шу ерга юборинг — "
            "тўлов тасдиқлангач мақола тайёрланиб юборилади."
        ),
        "need_receipt": (
            "📸 Илтимос, тўлов чекини <b>расм (фото)</b> кўринишида юборинг."
        ),
        "receipt_ok": "✅ Чек қабул қилинди. Мақола тайёрланмоқда...",
        "receipt_pending": (
            "✅ Чекингиз қабул қилинди!\n\n"
            "⏳ Тўлов текширилмоқда. Тасдиқлангач, мақола автоматик "
            "тайёрланиб юборилади. Илтимос, кутиб туринг."
        ),
        "payment_rejected": (
            "❌ Афсуски, тўлов тасдиқланмади.\n\n"
            "Илтимос, тўловни текшириб, чекни қайтадан юборинг ёки "
            "/new орқали янги буюртма беринг."
        ),
        "btn_approve": "✅ Тасдиқлаш",
        "btn_reject": "❌ Рад этиш",
        "admin_approved": "✅ Тасдиқланди — мақола тайёрланмоқда.",
        "admin_rejected": "❌ Рад этилди.",
        "already_handled": "Бу буюртма аллақачон кўриб чиқилган.",
        "your_id": (
            "🆔 Сизнинг Telegram ID: <code>{id}</code>\n\n"
            "Уни админ (эга) сифатида созлаш мумкин."
        ),
        "choose_method": (
            "💳 Тўлов усулини танланг.\n\n"
            "Мақола ҳажми: <b>{pages} бет</b>\n"
            "Жами тўлов: <b>{total} сўм</b>"
        ),
        "btn_payme": "💳 Payme",
        "btn_click": "💳 Click",
        "btn_card": "🧾 Карта + чек",
        "btn_pay": "💳 Тўлаш",
        "online_pay_msg": (
            "💳 Қуйидаги тугма орқали тўлов қилинг.\n"
            "Тўлов муваффақиятли бўлгач, мақола <b>автоматик</b> юборилади."
        ),
        "payment_confirmed": "✅ Тўлов қабул қилинди! Раҳмат.",
        "generating": (
            "⏳ Мақола тайёрланмоқда... Бу 1–3 дақиқа давом этиши мумкин.\n"
            "Илтимос, кутиб туринг."
        ),
        "done_text": "✅ Мақола тайёр! Қуйида матн ва Word (.docx) файли:",
        "after_delivery": (
            "🎉 Мақолангиз тайёр бўлди!\n\n"
            "🆕 Янги мақола буюртма қилиш учун пастдаги тугмани босинг.\n"
            "✍️ Фикр, шикоят ёки таклифингиз бўлса — биз билан боғланинг."
        ),
        "btn_new_article": "🆕 Янги мақола",
        "btn_feedback": "✍️ Шикоят / Таклиф",
        "docx_caption": "📄 Word форматидаги мақола",
        "error": "❌ Хатолик юз берди:\n<code>{err}</code>\nҚайтадан /new орқали уриниб кўринг.",
        "cancelled": "Бекор қилинди. Янги мақола учун /new юборинг.",
        "help": (
            "ℹ️ <b>Ёрдам</b>\n\n"
            "/new — янги илмий мақола ёзиш\n"
            "/status — буюртмаларингиз ҳолати\n"
            "/lang — интерфейс тилини ўзгартириш\n"
            "/cancel — жорий жараённи бекор қилиш\n"
            "/help — ушбу ёрдам\n\n"
            "Бот ОАК талаблари асосида мақола ва тезис тайёрлайди, Word ҳамда "
            "PDF файлда юборади.\n"
            "📄 Мақола — {article} сўм/бет\n"
            "📝 Тезис — {thesis} сўм/бет\n"
            "Тўловдан кейин иш тайёрланади."
        ),
        "lang_set": "✅ Тил ўзбекчага ўрнатилди.",
        "skip_hint": "(ўтказиб юбориш учун — белгисини юборинг)",
        "receipt_forwarded": (
            "🧾 Янги тўлов чеки!\n"
            "👤 Мижоз: {user}\n"
            "📄 Мавзу: {topic}\n"
            "📃 Ҳажм: {pages} бет\n"
            "💰 Сумма: {total} сўм"
        ),
        "pdf_caption": "📕 PDF форматидаги мақола",
        "status_empty": "Сизда ҳали буюртмалар йўқ. /new орқали бошланг.",
        "status_header": "📋 <b>Сўнгги буюртмаларингиз:</b>",
        "status_line": (
            "📄 {topic}\n"
            "📃 {pages} бет · 💰 {total} сўм\n"
            "📌 Ҳолат: {status}"
        ),
        "st_created": "⏳ Тўлов кутилмоқда",
        "st_paid": "✅ Тўланган",
        "st_delivering": "✍️ Тайёрланмоқда",
        "st_delivered": "📨 Юборилган",
        "st_cancelled": "❌ Бекор қилинган",
        "stats_denied": "⛔ Бу буйруқ фақат админ учун.",
        "stats_body": (
            "📊 <b>Статистика</b>\n\n"
            "Жами буюртмалар: <b>{total}</b>\n"
            "Тўланган: <b>{paid}</b>\n"
            "Юборилган: <b>{delivered}</b>\n"
            "Жами даромад: <b>{revenue} сўм</b>"
        ),
        # --- Faza 1: ish turi / til / dialog ---
        "choose_worktype": "🧩 <b>Иш турини танланг:</b>",
        "btn_article": "📄 Мақола",
        "btn_thesis": "📝 Тезис",
        "ask_work_language": "🌐 <b>Иш қайси тилда ёзилсин?</b>",
        "ask_field": (
            "🔬 <b>Илмий соҳани танланг</b> (ёки «Бошқа»ни босиб ўзингиз ёзинг):"
        ),
        "btn_field_other": "✍️ Бошқа",
        "ask_field_other": "🔬 Илмий соҳани (йўналишни) ёзинг:",
        "ask_author_full": (
            "✍️ <b>Муаллиф маълумотлари:</b>\n"
            "Ф.И.Ш., иш/ўқиш жойи, лавозим ёки мақом (талаба, магистрант, "
            "докторант, ўқитувчи…), e-mail.\n"
            "Ихтиёрий: ORCID, илмий раҳбар.\n\n"
            "Ҳаммасини бир хабарда ёзинг. Кераксиз бўлса <b>—</b> юборинг."
        ),
        "ask_extra": (
            "📎 <b>Қўшимча истаклар</b> (ихтиёрий):\n"
            "тадқиқот объекти/ҳудуди, журнал/конференция номи ва ҳ.к.\n"
            "Керак бўлмаса <b>—</b> юборинг."
        ),
        "confirm_summary": (
            "📋 <b>Буюртмани текширинг:</b>\n\n"
            "🧩 Тури: <b>{work}</b>\n"
            "🌐 Тил: <b>{wlang}</b>\n"
            "📌 Мавзу: {topic}\n"
            "🔬 Соҳа: {field}\n"
            "✍️ Муаллиф: {author}\n"
            "🏷 Калит сўзлар: {keywords}\n"
            "📄 Ҳажм: <b>{pages} бет</b>\n"
            "📎 Қўшимча: {extra}\n\n"
            "💰 Жами: <b>{total} сўм</b>"
        ),
        "btn_confirm": "✅ Тасдиқлаш",
        "btn_edit": "✏️ Ўзгартириш",
        "wt_article": "Мақола",
        "wt_thesis": "Тезис",
    },
    "ru": {
        "choose_language": "Тилни танланг / Выберите язык:",
        "welcome": (
            "👋 Здравствуйте!\n\n"
            "Я бот, который пишет <b>научные статьи по требованиям ВАК (ОАК)</b>.\n\n"
            "Статья готовится по следующей структуре:\n"
            "• УДК\n"
            "• Заголовок\n"
            "• Аннотация и ключевые слова (узб., рус., англ.)\n"
            "• Введение\n"
            "• Основная часть (анализ и методы)\n"
            "• Результаты и их обсуждение\n"
            "• Заключение\n"
            "• Список использованной литературы\n\n"
            "Чтобы начать, отправьте команду /new."
        ),
        "menu_new": "📝 Написать новую статью — /new",
        "menu_lang": "🌐 Сменить язык — /lang",
        "menu_help": "ℹ️ Помощь — /help",
        "ask_topic": (
            "📌 <b>1/4</b> Введите тему статьи.\n\n"
            "Например: <i>«Развитие малого бизнеса в условиях цифровой экономики»</i>"
        ),
        "ask_field": (
            "🔬 <b>2/4</b> Введите научную область (направление).\n\n"
            "Например: <i>экономика, педагогика, информационные технологии, медицина...</i>"
        ),
        "ask_author": (
            "✍️ <b>3/4</b> Введите данные автора "
            "(Ф.И.О., должность, организация).\n\n"
            "Например: <i>Каримов А.А., базовый докторант, ТГЭУ</i>\n\n"
            "Если не нужно — отправьте символ <b>—</b>."
        ),
        "ask_keywords": (
            "🏷 <b>4/5</b> Введите ключевые слова (через запятую).\n\n"
            "Если хотите, чтобы бот подобрал сам — отправьте символ <b>—</b>."
        ),
        "ask_pages": (
            "📄 <b>5/5</b> Сколько страниц должна быть статья?\n\n"
            "Введите число от {min} до {max}."
        ),
        "choose_kind": (
            "🧩 Выберите тип статьи ({pages} стр.):\n\n"
            "📄 <b>Обычная</b> — текст, аннотация и литература.\n"
            "    Цена: <b>{std} сум</b>\n\n"
            "📊 <b>Premium</b> — с таблицами и диаграммами.\n"
            "    Цена: <b>{prem} сум</b>"
        ),
        "btn_kind_standard": "📄 Обычная",
        "btn_kind_premium": "📊 Premium (таблицы+диаграммы)",
        "invalid_pages": (
            "⚠️ Пожалуйста, введите целое число от {min} до {max}."
        ),
        "payment_info": (
            "💳 <b>Оплата</b>\n\n"
            "Объём статьи: <b>{pages} стр.</b>\n"
            "Итого к оплате: <b>{total} сум</b>\n\n"
            "Переведите оплату на пластиковую карту:\n"
            "💳 <code>{card}</code>\n"
            "👤 {holder}\n\n"
            "После оплаты отправьте сюда <b>чек об оплате (скриншот/фото)</b> — "
            "после подтверждения оплаты статья будет подготовлена и отправлена."
        ),
        "need_receipt": (
            "📸 Пожалуйста, отправьте чек об оплате в виде <b>изображения (фото)</b>."
        ),
        "receipt_ok": "✅ Чек принят. Статья готовится...",
        "receipt_pending": (
            "✅ Ваш чек принят!\n\n"
            "⏳ Оплата проверяется. После подтверждения статья будет "
            "подготовлена и отправлена автоматически. Пожалуйста, подождите."
        ),
        "payment_rejected": (
            "❌ К сожалению, оплата не подтверждена.\n\n"
            "Пожалуйста, проверьте оплату и отправьте чек снова или "
            "оформите новый заказ через /new."
        ),
        "btn_approve": "✅ Подтвердить",
        "btn_reject": "❌ Отклонить",
        "admin_approved": "✅ Подтверждено — статья готовится.",
        "admin_rejected": "❌ Отклонено.",
        "already_handled": "Этот заказ уже обработан.",
        "your_id": (
            "🆔 Ваш Telegram ID: <code>{id}</code>\n\n"
            "Его можно указать как админ (владелец)."
        ),
        "choose_method": (
            "💳 Выберите способ оплаты.\n\n"
            "Объём статьи: <b>{pages} стр.</b>\n"
            "Итого к оплате: <b>{total} сум</b>"
        ),
        "btn_payme": "💳 Payme",
        "btn_click": "💳 Click",
        "btn_card": "🧾 Карта + чек",
        "btn_pay": "💳 Оплатить",
        "online_pay_msg": (
            "💳 Оплатите по кнопке ниже.\n"
            "После успешной оплаты статья будет отправлена <b>автоматически</b>."
        ),
        "payment_confirmed": "✅ Оплата принята! Спасибо.",
        "generating": (
            "⏳ Статья готовится... Это может занять 1–3 минуты.\n"
            "Пожалуйста, подождите."
        ),
        "done_text": "✅ Статья готова! Ниже текст и файл Word (.docx):",
        "after_delivery": (
            "🎉 Ваша статья готова!\n\n"
            "🆕 Чтобы заказать новую статью, нажмите кнопку ниже.\n"
            "✍️ Если есть отзыв, жалоба или предложение — свяжитесь с нами."
        ),
        "btn_new_article": "🆕 Новая статья",
        "btn_feedback": "✍️ Жалоба / Предложение",
        "docx_caption": "📄 Статья в формате Word",
        "error": "❌ Произошла ошибка:\n<code>{err}</code>\nПопробуйте снова через /new.",
        "cancelled": "Отменено. Для новой статьи отправьте /new.",
        "help": (
            "ℹ️ <b>Помощь</b>\n\n"
            "/new — написать новую научную статью\n"
            "/status — статус ваших заказов\n"
            "/lang — сменить язык интерфейса\n"
            "/cancel — отменить текущий процесс\n"
            "/help — эта справка\n\n"
            "Бот готовит статьи и тезисы по требованиям ВАК (ОАК) "
            "и отправляет их в виде файлов Word и PDF.\n"
            "📄 Статья — {article} сум/стр.\n"
            "📝 Тезис — {thesis} сум/стр.\n"
            "После оплаты работа готовится."
        ),
        "lang_set": "✅ Язык установлен на русский.",
        "skip_hint": "(чтобы пропустить — отправьте символ —)",
        "receipt_forwarded": (
            "🧾 Новый чек об оплате!\n"
            "👤 Клиент: {user}\n"
            "📄 Тема: {topic}\n"
            "📃 Объём: {pages} стр.\n"
            "💰 Сумма: {total} сум"
        ),
        "pdf_caption": "📕 Статья в формате PDF",
        "status_empty": "У вас пока нет заказов. Начните через /new.",
        "status_header": "📋 <b>Ваши последние заказы:</b>",
        "status_line": (
            "📄 {topic}\n"
            "📃 {pages} стр. · 💰 {total} сум\n"
            "📌 Статус: {status}"
        ),
        "st_created": "⏳ Ожидает оплаты",
        "st_paid": "✅ Оплачено",
        "st_delivering": "✍️ Готовится",
        "st_delivered": "📨 Отправлено",
        "st_cancelled": "❌ Отменено",
        "stats_denied": "⛔ Эта команда только для админа.",
        "stats_body": (
            "📊 <b>Статистика</b>\n\n"
            "Всего заказов: <b>{total}</b>\n"
            "Оплачено: <b>{paid}</b>\n"
            "Отправлено: <b>{delivered}</b>\n"
            "Общий доход: <b>{revenue} сум</b>"
        ),
        # --- Фаза 1 ---
        "choose_worktype": "🧩 <b>Выберите тип работы:</b>",
        "btn_article": "📄 Статья",
        "btn_thesis": "📝 Тезис",
        "ask_work_language": "🌐 <b>На каком языке подготовить работу?</b>",
        "ask_field": (
            "🔬 <b>Выберите научную область</b> (или нажмите «Другое» и впишите):"
        ),
        "btn_field_other": "✍️ Другое",
        "ask_field_other": "🔬 Впишите научную область (направление):",
        "ask_author_full": (
            "✍️ <b>Данные автора:</b>\n"
            "Ф.И.О., место работы/учёбы, должность или статус (студент, магистрант, "
            "докторант, преподаватель…), e-mail.\n"
            "Необязательно: ORCID, научный руководитель.\n\n"
            "Напишите всё одним сообщением. Если не нужно — отправьте <b>—</b>."
        ),
        "ask_extra": (
            "📎 <b>Дополнительные пожелания</b> (необязательно):\n"
            "объект/регион исследования, название журнала/конференции и т.д.\n"
            "Если не нужно — отправьте <b>—</b>."
        ),
        "confirm_summary": (
            "📋 <b>Проверьте заказ:</b>\n\n"
            "🧩 Тип: <b>{work}</b>\n"
            "🌐 Язык: <b>{wlang}</b>\n"
            "📌 Тема: {topic}\n"
            "🔬 Область: {field}\n"
            "✍️ Автор: {author}\n"
            "🏷 Ключевые слова: {keywords}\n"
            "📄 Объём: <b>{pages} стр.</b>\n"
            "📎 Дополнительно: {extra}\n\n"
            "💰 Итого: <b>{total} сум</b>"
        ),
        "btn_confirm": "✅ Подтвердить",
        "btn_edit": "✏️ Изменить",
        "wt_article": "Статья",
        "wt_thesis": "Тезис",
    },
    "en": {
        "choose_language": "Тилни танланг / Выберите язык / Choose language:",
        "welcome": (
            "👋 Hello!\n\n"
            "I am a bot that writes <b>scientific articles and theses</b> "
            "to OAK (VAK) standards.\n\n"
            "To start, send /new."
        ),
        "ask_topic": (
            "📌 Enter the <b>topic</b> of the work.\n\n"
            "For example: <i>«Development of small business in the digital economy»</i>"
        ),
        "invalid_pages": "⚠️ Please enter a whole number between {min} and {max}.",
        "payment_info": (
            "💳 <b>Payment</b>\n\n"
            "Volume: <b>{pages} pages</b>\n"
            "Total: <b>{total} sum</b>\n\n"
            "Transfer to the card below:\n"
            "💳 <code>{card}</code>\n"
            "👤 {holder}\n\n"
            "After paying, send the <b>receipt (screenshot/photo)</b> here — "
            "the work will be prepared once the payment is confirmed."
        ),
        "need_receipt": "📸 Please send the payment receipt as an <b>image (photo)</b>.",
        "receipt_ok": "✅ Receipt received. Preparing the work...",
        "receipt_pending": (
            "✅ Your receipt has been received!\n\n"
            "⏳ Payment is being verified. Once confirmed, the work will be "
            "prepared and sent automatically. Please wait."
        ),
        "payment_rejected": (
            "❌ Unfortunately, the payment was not confirmed.\n\n"
            "Please check the payment and resend the receipt, or start a new "
            "order via /new."
        ),
        "btn_approve": "✅ Approve",
        "btn_reject": "❌ Reject",
        "admin_approved": "✅ Approved — the work is being prepared.",
        "admin_rejected": "❌ Rejected.",
        "already_handled": "This order has already been handled.",
        "your_id": "🆔 Your Telegram ID: <code>{id}</code>",
        "choose_method": (
            "💳 Choose a payment method.\n\n"
            "Volume: <b>{pages} pages</b>\n"
            "Total: <b>{total} sum</b>"
        ),
        "btn_payme": "💳 Payme",
        "btn_click": "💳 Click",
        "btn_card": "🧾 Card + receipt",
        "btn_pay": "💳 Pay",
        "online_pay_msg": (
            "💳 Pay via the button below.\n"
            "After a successful payment the work will be sent <b>automatically</b>."
        ),
        "payment_confirmed": "✅ Payment received! Thank you.",
        "generating": (
            "⏳ Preparing the work... This may take 1–3 minutes.\nPlease wait."
        ),
        "done_text": "✅ Done! Below is the text and the Word (.docx) file:",
        "after_delivery": (
            "🎉 Your work is ready!\n\n"
            "🆕 To order a new work, tap the button below.\n"
            "✍️ For feedback, a complaint or a suggestion — contact us."
        ),
        "btn_new_article": "🆕 New work",
        "btn_feedback": "✍️ Complaint / Suggestion",
        "docx_caption": "📄 Work in Word format",
        "pdf_caption": "📕 Work in PDF format",
        "error": "❌ An error occurred:\n<code>{err}</code>\nTry again via /new.",
        "cancelled": "Cancelled. Send /new for a new work.",
        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "/new — order a new article or thesis\n"
            "/status — your orders\n"
            "/lang — change interface language\n"
            "/cancel — cancel the current process\n"
            "/help — this help\n\n"
            "The bot prepares the work to OAK (VAK) standards and sends Word and "
            "PDF files."
        ),
        "lang_set": "✅ Language set to English.",
        "receipt_forwarded": (
            "🧾 New payment receipt!\n"
            "👤 Client: {user}\n"
            "📄 Topic: {topic}\n"
            "📃 Volume: {pages} pages\n"
            "💰 Amount: {total} sum"
        ),
        "status_empty": "You have no orders yet. Start via /new.",
        "status_header": "📋 <b>Your recent orders:</b>",
        "status_line": (
            "📄 {topic}\n📃 {pages} pages · 💰 {total} sum\n📌 Status: {status}"
        ),
        "st_created": "⏳ Awaiting payment",
        "st_paid": "✅ Paid",
        "st_delivering": "✍️ Preparing",
        "st_delivered": "📨 Sent",
        "st_cancelled": "❌ Cancelled",
        "stats_denied": "⛔ This command is for the admin only.",
        "stats_body": (
            "📊 <b>Statistics</b>\n\n"
            "Total orders: <b>{total}</b>\n"
            "Paid: <b>{paid}</b>\n"
            "Sent: <b>{delivered}</b>\n"
            "Total revenue: <b>{revenue} sum</b>"
        ),
        "choose_worktype": "🧩 <b>Choose the type of work:</b>",
        "btn_article": "📄 Article",
        "btn_thesis": "📝 Thesis",
        "ask_work_language": "🌐 <b>In which language should the work be written?</b>",
        "ask_field": (
            "🔬 <b>Choose the scientific field</b> (or tap «Other» to type it):"
        ),
        "btn_field_other": "✍️ Other",
        "ask_field_other": "🔬 Type the scientific field (specialization):",
        "ask_author_full": (
            "✍️ <b>Author details:</b>\n"
            "Full name, workplace/university, position or status (student, master's "
            "student, PhD student, teacher…), e-mail.\n"
            "Optional: ORCID, supervisor.\n\n"
            "Send it all in one message. If not needed, send <b>—</b>."
        ),
        "ask_keywords": (
            "🏷 Enter <b>keywords</b> (comma-separated).\n\n"
            "To let the bot choose, send <b>—</b>."
        ),
        "ask_pages": (
            "📄 How many pages should the work be?\n\n"
            "Enter a number between {min} and {max}."
        ),
        "ask_extra": (
            "📎 <b>Additional wishes</b> (optional):\n"
            "research object/region, journal/conference name, etc.\n"
            "If not needed, send <b>—</b>."
        ),
        "confirm_summary": (
            "📋 <b>Please review your order:</b>\n\n"
            "🧩 Type: <b>{work}</b>\n"
            "🌐 Language: <b>{wlang}</b>\n"
            "📌 Topic: {topic}\n"
            "🔬 Field: {field}\n"
            "✍️ Author: {author}\n"
            "🏷 Keywords: {keywords}\n"
            "📄 Volume: <b>{pages} pages</b>\n"
            "📎 Additional: {extra}\n\n"
            "💰 Total: <b>{total} sum</b>"
        ),
        "btn_confirm": "✅ Confirm",
        "btn_edit": "✏️ Edit",
        "wt_article": "Article",
        "wt_thesis": "Thesis",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """Tarjima matnini olish; til topilmasa o'zbekchaga qaytadi."""
    lang = lang if lang in TEXTS else "uz"
    text = TEXTS[lang].get(key, TEXTS["uz"].get(key, key))
    return text.format(**kwargs) if kwargs else text
