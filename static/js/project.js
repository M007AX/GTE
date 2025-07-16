document.getElementById('continue-btn').addEventListener('click', async function() {
    const btn = this;
    btn.disabled = true;
    btn.textContent = 'Сохранение...';

    try {
        // 1. Собираем все данные
        const tableData = { weather: [], workdays: [] };

        document.querySelectorAll('.editable').forEach(input => {
            let hour = parseInt(input.dataset.hour.split(':')[0]);
            hour = hour === 23 ? 0 : hour + 1;

            tableData.weather.push({
                location: input.dataset.location,
                hour: hour,
                param: input.dataset.param,
                value: input.value
            });
        });

        // 2. Отправляем на сервер
        const response = await fetch('/save-and-predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(tableData)
        });

        if (!response.ok) {
            throw new Error('Ошибка сохранения данных');
        }

        // 3. Переходим на страницу прогноза
        window.location.href = '/predict';

    } catch (error) {
        alert(error.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Далее →';
    }
});