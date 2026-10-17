// Форма, A/B-вариант и счётчики на главной странице.
(function () {
  var form = document.getElementById('lead-form');
  var okBox = document.getElementById('form-ok');
  var errBox = document.getElementById('form-error');
  var submit = document.getElementById('submit');
  var params = new URLSearchParams(location.search);
  var variant = 'A';

  var HEADLINES = {
    A: 'Заявки с сайта — в одном месте',
    B: 'Форма, которая не теряет заявки'
  };
  var SUBLINES = {
    A: 'Форма проверяет ввод, сервер хранит заявки, админка показывает их списком. Заголовок на этой странице меняется по A/B-тесту — счётчики видны в статистике.',
    B: 'Проверка на сервере, защита от повторных отправок, UTM-метки в каждой заявке. Заголовок выбирается A/B-тестом: вам достался один из двух вариантов.'
  };

  function clearErrors() {
    document.querySelectorAll('.field__err').forEach(function (el) { el.textContent = ''; });
    document.querySelectorAll('.field input, .field textarea').forEach(function (el) { el.classList.remove('is-error'); });
    errBox.textContent = '';
    okBox.classList.remove('is-on');
  }

  function showErrors(errors) {
    Object.keys(errors || {}).forEach(function (key) {
      var slot = document.querySelector('[data-for="' + key + '"]');
      if (slot) {
        slot.textContent = errors[key];
        var input = document.getElementById(key);
        if (input) input.classList.add('is-error');
      }
    });
    if (errors && errors.form) errBox.textContent = errors.form;
  }

  document.querySelectorAll('.field input, .field textarea').forEach(function (el) {
    el.addEventListener('input', function () {
      el.classList.remove('is-error');
      var slot = document.querySelector('[data-for="' + el.id + '"]');
      if (slot) slot.textContent = '';
    });
  });

  function loadVariant() {
    fetch('/api/variant').then(function (r) { return r.json(); }).then(function (data) {
      variant = data.variant;
      document.getElementById('headline').textContent = HEADLINES[variant];
      document.getElementById('subline').textContent = SUBLINES[variant];
      document.getElementById('stat-variant').textContent = variant;
      document.body.dataset.variant = variant;
    }).catch(function () {});
  }

  function loadStats() {
    fetch('/api/public-stats').then(function (r) { return r.json(); }).then(function (data) {
      document.getElementById('stat-views').textContent = data.views;
      document.getElementById('stat-leads').textContent = data.leads;
      document.getElementById('stat-conv').textContent = Number(data.best_conversion).toFixed(1).replace('.', ',');
    }).catch(function () {});
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearErrors();
    submit.disabled = true;
    submit.textContent = 'Отправляем…';

    var payload = {
      name: document.getElementById('name').value,
      contact: document.getElementById('contact').value,
      message: document.getElementById('message').value,
      utm_source: params.get('utm_source') || '',
      utm_campaign: params.get('utm_campaign') || '',
      variant: variant
    };

    fetch('/api/leads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function (r) {
      return r.json().then(function (data) { return { status: r.status, data: data }; });
    }).then(function (res) {
      if (res.status === 201 && res.data.ok) {
        okBox.classList.add('is-on');
        document.getElementById('lead-id').textContent = res.data.id;
        form.reset();
        loadStats();
        return;
      }
      showErrors(res.data.errors || { form: 'Не получилось отправить. Попробуйте ещё раз.' });
    }).catch(function () {
      errBox.textContent = 'Сервер не ответил. Проверьте соединение.';
    }).finally(function () {
      submit.disabled = false;
      submit.textContent = 'Отправить заявку';
    });
  });

  loadVariant();
  loadStats();
})();
