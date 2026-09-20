(function(w){'use strict';
  function div(a,b){return Math.floor(a/b)}
  function toJalali(gy,gm,gd){var gdm=[0,31,59,90,120,151,181,212,243,273,304,334],jy=gy<=1600?0:979;gy-=gy<=1600?621:1600;var gy2=gm>2?gy+1:gy;var days=365*gy+div(gy2+3,4)-div(gy2+99,100)+div(gy2+399,400)-80+gd+gdm[gm-1];jy+=33*div(days,12053);days%=12053;jy+=4*div(days,1461);days%=1461;if(days>365){jy+=div(days-1,365);days=(days-1)%365}var jm=days<186?1+div(days,31):7+div(days-186,30);var jd=1+(days<186?days%31:(days-186)%30);return[jy,jm,jd]}
  function fromJalali(jy,jm,jd){var gy=jy<=979?621:1600, y=jy-(jy<=979?0:979), days=365*y+div(y,33)*8+div((y%33)+3,4)+(jy<=979?0:79)+jd-1+(jm<7?(jm-1)*31:(jm-7)*30+186), gd=days%146097;var g=gy+400*div(days,146097);if(gd>36524){g+=100*div(--gd,36524);gd%=36524;if(gd>=365)gd++}g+=4*div(gd,1461);gd%=1461;if(gd>365){g+=div(gd-1,365);gd=(gd-1)%365}var gm=1, md=[31,(g%4===0&&g%100!==0)||g%400===0?29:28,31,30,31,30,31,31,30,31,30,31];while(gd>=md[gm-1]){gd-=md[gm-1];gm++}return[g,gm,gd+1]}
  w.Jalali={toJalali:toJalali,fromJalali:fromJalali};
})(window);
