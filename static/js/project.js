document.addEventListener('DOMContentLoaded', function() {
    // Save button event listener
    const saveBtn = document.getElementById('save-changes');
    if (saveBtn) {
        saveBtn.addEventListener('click', () => saveTableData(false));
    }

    // Continue button event listener
    const continueBtn = document.querySelector('.btn-continue');
    if (continueBtn) {
        continueBtn.addEventListener('click', function(e) {
            e.preventDefault();
            saveTableData(true);
        });
    }
});

function saveTableData(shouldContinue = false) {
    try {
        // Get the date info from the page
        const dateStr = document.querySelector('h1').textContent.replace('Прогноз на ', '').trim();
        const dayOfWeek = document.querySelector('p').textContent.match(/День недели: (\d)/)[1];
        const weekOfYear = document.querySelector('p').textContent.match(/Неделя года: (\d+)/)[1];

        // Prepare the data structure
        const weatherData = [];

        // Get all rows in the table body
        const rows = document.querySelectorAll('.weather-table tbody tr');

        rows.forEach(row => {
            const hourCell = row.querySelector('.sticky-column');
            const hourText = hourCell.textContent.split(':')[0].padStart(2, '0');
            const hourNum = parseInt(hourText);

            // Get workday status
            const workdaySelect = row.querySelector('.editable-workday');
            const isWorkday = workdaySelect ? workdaySelect.value : '1';

            // Get lag_24 value from the previous day fact column (5th td in the row)
            const lagCell = row.querySelector('td:nth-child(5)');
            let lagValue = '0';
            if (lagCell && lagCell.textContent && lagCell.textContent !== '-') {
                lagValue = lagCell.textContent.trim();
            }

            // Create the base data object for this hour
            const hourData = {
                Час: hourNum,
                День_недели: parseInt(dayOfWeek),
                Неделя_года: parseInt(weekOfYear),
                Рабочий_день: parseInt(isWorkday),
                lag_24: parseFloat(lagValue) || 0
            };

            // Get all location data for this hour
            const inputs = row.querySelectorAll('.editable');
            inputs.forEach(input => {
                const location = input.dataset.location;
                const param = input.dataset.param;
                const value = input.value === '-' ? '0' : input.value;

                // Create parameter names as expected by the model
                const paramName = `${location}_${param}`;
                hourData[paramName] = parseFloat(value) || 0;
            });

            weatherData.push(hourData);
        });

        // Convert to CSV format
        const csvData = convertToCSV(weatherData);

        // Send data to server
        fetch('/save-weather-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                date: dateStr,
                data: weatherData,
                csv: csvData
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(text || 'Server error');
                });
            }
            return response.json();
        })
        .then(data => {
            if (data && data.success) {
                if (shouldContinue) {
                    window.location.href = document.querySelector('.btn-continue').href;
                } else {
                    alert('Данные успешно сохранены!');
                }
            } else {
                alert('Ошибка при сохранении данных: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Ошибка при сохранении данных: ' + error.message);
        });
    } catch (error) {
        console.error('Error in saveTableData:', error);
        alert('Ошибка при обработке данных: ' + error.message);
    }
}

function convertToCSV(data) {
    if (!data || data.length === 0) return '';

    // Get all unique keys (column names)
    const headers = new Set();
    data.forEach(row => {
        Object.keys(row).forEach(key => headers.add(key));
    });

    const headerArray = Array.from(headers);

    // Create CSV header
    let csv = headerArray.join(',') + '\n';

    // Add rows
    data.forEach(row => {
        const rowValues = headerArray.map(header => {
            return row[header] !== undefined ? row[header] : '';
        });
        csv += rowValues.join(',') + '\n';
    });

    return csv;
}