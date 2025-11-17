(function(){
  var didReload = false;
  function pad(n){return n<10?"0"+n:String(n)}
  function format(ms){
    if(ms<0) ms=0;
    var total=Math.floor(ms/1000);
    var m=Math.floor(total/60);
    var s=total%60;
    return pad(m)+":"+pad(s);
  }
  function tick(){
    var now=Date.now();
    document.querySelectorAll('[data-expires]').forEach(function(el){
      var until = Date.parse(el.getAttribute('data-expires'));
      if(!until) return;
      var left = until - now;
      el.textContent = format(left);
      if(left<=0){
        el.classList.add('expired');
        if(!didReload && el.getAttribute('data-refresh-when-expired') === 'true' && document.visibilityState === 'visible'){
          didReload = true;
          setTimeout(function(){ location.reload(); }, 300);
        }
      }
    });
    requestAnimationFrame(tick);
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded', tick);
  } else {
    tick();
  }
})();