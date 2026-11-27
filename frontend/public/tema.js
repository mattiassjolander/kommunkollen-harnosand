// Sparat val av ljust eller mörkt läge sätts innan sidan ritas (se Temavaljare.vue).
try {
  var tema = localStorage.getItem('kommunkollen-tema')
  if (tema === 'morkt') document.documentElement.dataset.theme = 'dark'
  if (tema === 'ljust') document.documentElement.dataset.theme = 'light'
} catch (e) {}
