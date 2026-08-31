// app/static/js/patient_quiz.js
(function () {
    function initQuizBlock(block) {
        const questions = Array.from(block.querySelectorAll(".cl-quiz-question"));
        if (questions.length < 2) return;

        let current = 0;

        const progressWrap = document.createElement("div");
        progressWrap.className = "cl-quiz-stepper-progress";
        progressWrap.innerHTML = `
            <div class="cl-quiz-stepper-label">سوال <span data-current>1</span> از <span data-total>${questions.length}</span></div>
            <div class="cl-progress-track"><div class="cl-progress-fill" data-fill style="width:0%;"></div></div>
        `;
        block.insertBefore(progressWrap, questions[0]);

        const navRow = document.createElement("div");
        navRow.className = "cl-quiz-stepper-nav";
        navRow.innerHTML = `
            <button type="button" class="cl-btn cl-btn-sm cl-btn-outline" data-prev disabled>قبلی</button>
            <button type="button" class="cl-btn cl-btn-sm" data-next disabled>سوال بعدی</button>
        `;
        block.appendChild(navRow);

        const summary = document.createElement("div");
        summary.className = "cl-quiz-stepper-summary";
        summary.style.display = "none";
        block.appendChild(summary);

        function showQuestion(idx) {
            questions.forEach(function (q, i) { q.style.display = (i === idx) ? "" : "none"; });
            progressWrap.querySelector("[data-current]").textContent = idx + 1;
            progressWrap.querySelector("[data-fill]").style.width = Math.round(((idx + 1) / questions.length) * 100) + "%";
            navRow.querySelector("[data-prev]").disabled = idx === 0;
            const nextBtn = navRow.querySelector("[data-next]");
            nextBtn.disabled = questions[idx].dataset.answered !== "true";
            nextBtn.textContent = idx === questions.length - 1 ? "مشاهده نتیجه" : "سوال بعدی";
        }

        function showSummary() {
            questions.forEach(function (q) { q.style.display = "none"; });
            navRow.style.display = "none";
            progressWrap.style.display = "none";
            let correct = 0;
            questions.forEach(function (q) {
                const resultEl = q.querySelector(".cl-quiz-result");
                if (resultEl && resultEl.classList.contains("cl-quiz-result-correct")) correct++;
            });
            summary.style.display = "block";
            summary.innerHTML = `
                <div class="cl-quiz-summary-score">${correct} از ${questions.length}</div>
                <p class="cl-sub">پاسخ‌های درست شما</p>
            `;
        }

        navRow.querySelector("[data-prev]").addEventListener("click", function () {
            if (current > 0) { current--; showQuestion(current); }
        });
        navRow.querySelector("[data-next]").addEventListener("click", function () {
            if (current < questions.length - 1) { current++; showQuestion(current); }
            else { showSummary(); }
        });

        questions.forEach(function (q, idx) {
            const observer = new MutationObserver(function () {
                if (q.dataset.answered === "true" && idx === current) {
                    navRow.querySelector("[data-next]").disabled = false;
                }
            });
            observer.observe(q, { attributes: true, attributeFilter: ["data-answered"] });
        });

        showQuestion(0);
    }

    document.querySelectorAll(".cl-quiz-block").forEach(initQuizBlock);
})();