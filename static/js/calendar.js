// static/js/calendar.js
class DatePicker {
  constructor(options) {
    this.datePicker = document.getElementById(options.datePickerId);
    this.dateDisplay = document.querySelector(options.dateDisplaySelector);
    this.datePickerPopup = document.getElementById(options.popupId);
    this.currentMonthYear = document.getElementById(options.monthYearId);
    this.calendarDays = document.getElementById(options.calendarDaysId);
    this.prevMonthBtn = document.getElementById(options.prevMonthBtnId);
    this.nextMonthBtn = document.getElementById(options.nextMonthBtnId);

    // Устанавливаем текущую дату из URL или сегодняшнюю дату
    this.currentDate = this.getDateFromUrl() || new Date();
    this.currentMonth = this.currentDate.getMonth();
    this.currentYear = this.currentDate.getFullYear();

    this.monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                      'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

    this.init();
  }

  // Получаем дату из URL
  getDateFromUrl() {
    const pathParts = window.location.pathname.split('/');
    if (pathParts.length >= 3) {
      const dateStr = pathParts[2];
      const [day, month, year] = dateStr.split('-').map(Number);
      if (day && month && year) {
        return new Date(year, month - 1, day);
      }
    }
    return null;
  }

  init() {
    this.setupEventListeners();
    this.updateDisplay();
  }

  setupEventListeners() {
    if (this.datePicker) {
      this.datePicker.addEventListener('click', (e) => {
        e.stopPropagation();
        this.toggleCalendar();
      });
    }

    if (this.prevMonthBtn) {
      this.prevMonthBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.changeMonth(-1);
      });
    }

    if (this.nextMonthBtn) {
      this.nextMonthBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.changeMonth(1);
      });
    }

    document.addEventListener('click', () => this.hideCalendar());

    if (this.datePickerPopup) {
      this.datePickerPopup.addEventListener('click', (e) => e.stopPropagation());
    }
  }

  updateDisplay() {
    if (this.dateDisplay) {
      const day = this.currentDate.getDate().toString().padStart(2, '0');
      const month = (this.currentDate.getMonth() + 1).toString().padStart(2, '0');
      const year = this.currentDate.getFullYear();
      this.dateDisplay.textContent = `${day}.${month}.${year}`;
    }
  }

  toggleCalendar() {
    if (this.datePickerPopup.classList.contains('show')) {
      this.hideCalendar();
    } else {
      this.showCalendar();
    }
  }

  showCalendar() {
    if (!this.datePickerPopup || !this.datePicker) return;

    const rect = this.datePicker.getBoundingClientRect();
    this.datePickerPopup.style.left = `${rect.left}px`;
    this.datePickerPopup.style.top = `${rect.bottom + window.scrollY}px`;

    this.datePickerPopup.classList.add('show');
    this.renderCalendar();
  }

  hideCalendar() {
    if (this.datePickerPopup) {
      this.datePickerPopup.classList.remove('show');
    }
  }

  changeMonth(offset) {
    let newMonth = this.currentMonth + offset;
    let newYear = this.currentYear;

    if (newMonth > 11) {
      newMonth = 0;
      newYear++;
    } else if (newMonth < 0) {
      newMonth = 11;
      newYear--;
    }

    this.currentMonth = newMonth;
    this.currentYear = newYear;
    this.renderCalendar();
  }

  renderCalendar() {
    if (!this.currentMonthYear || !this.calendarDays) return;

    this.currentMonthYear.textContent = `${this.monthNames[this.currentMonth]} ${this.currentYear}`;

    const firstDay = new Date(this.currentYear, this.currentMonth, 1).getDay();
    const daysInMonth = new Date(this.currentYear, this.currentMonth + 1, 0).getDate();

    let date = 1;
    let html = '';
    let firstDayAdjusted = firstDay === 0 ? 6 : firstDay - 1;

    for (let i = 0; i < 6; i++) {
      if (date > daysInMonth) break;

      html += '<tr>';

      for (let j = 0; j < 7; j++) {
        if (i === 0 && j < firstDayAdjusted) {
          html += '<td></td>';
        } else if (date > daysInMonth) {
          html += '<td></td>';
        } else {
          const isSelected = (date === this.currentDate.getDate() &&
                            this.currentMonth === this.currentDate.getMonth() &&
                            this.currentYear === this.currentDate.getFullYear());
          const dateClass = isSelected ? 'selected' : '';
          html += `<td class="${dateClass}" data-date="${date}.${this.currentMonth + 1}.${this.currentYear}">${date}</td>`;
          date++;
        }
      }

      html += '</tr>';
    }

    this.calendarDays.innerHTML = html;

    document.querySelectorAll('#calendarDays td[data-date]').forEach(td => {
      td.addEventListener('click', (e) => {
        e.stopPropagation();
        this.handleDateSelection(td.getAttribute('data-date'));
      });
    });
  }

  handleDateSelection(selectedDate) {
    const [day, month, year] = selectedDate.split('.');
    const formattedDate = `${day}-${month}-${year}`;
    const pathParts = window.location.pathname.split('/');
    const currentPath = pathParts[1] || 'project';
    window.location.href = `/${currentPath}/${formattedDate}`;
  }
}

// Инициализация календаря при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
  // Проверяем, есть ли необходимые элементы на странице
  if (document.getElementById('datePicker') && document.getElementById('datePickerPopup')) {
    new DatePicker({
      datePickerId: 'datePicker',
      dateDisplaySelector: '.date-display',
      popupId: 'datePickerPopup',
      monthYearId: 'currentMonthYear',
      calendarDaysId: 'calendarDays',
      prevMonthBtnId: 'prevMonth',
      nextMonthBtnId: 'nextMonth'
    });
  }
});