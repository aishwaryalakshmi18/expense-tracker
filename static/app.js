const palette=['#159d86','#6c63e8','#f2b84b','#e87da5','#5e9ce6','#9a75d8','#91a3b0'];
function inr(n){return new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format(Number(n||0));}
function makeDonut(canvasId,legendId,labels,values){
 const canvas=document.getElementById(canvasId); if(!canvas||!labels.length)return;
 const colors=labels.map((_,i)=>palette[i%palette.length]); const total=values.reduce((a,b)=>a+Number(b||0),0);
 new Chart(canvas,{type:'doughnut',data:{labels,datasets:[{data:values,backgroundColor:colors,borderColor:'#fff',borderWidth:4,hoverOffset:7,borderRadius:5,spacing:2}]},
 options:{responsive:true,maintainAspectRatio:true,cutout:'72%',plugins:{legend:{display:false},tooltip:{backgroundColor:'#172832',padding:12,callbacks:{label:c=>` ${inr(c.raw)} · ${total?(c.raw/total*100).toFixed(1):0}%`}}},animation:{duration:650}}});
 const legend=document.getElementById(legendId); if(legend)legend.innerHTML=labels.map((label,i)=>`<div class="legend-row"><span class="dot" style="background:${colors[i]}"></span><span class="legend-name">${safe(label)}<small>${total?(values[i]/total*100).toFixed(1):0}%</small></span><b>${inr(values[i])}</b></div>`).join('');
}
function makeTrend(id,labels,values){const el=document.getElementById(id);if(!el)return;new Chart(el,{type:'line',data:{labels,datasets:[{label:'Paid spending',data:values,borderColor:'#159d86',backgroundColor:'rgba(21,157,134,.10)',fill:true,tension:.35,borderWidth:3,pointRadius:4,pointBackgroundColor:'#159d86'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' '+inr(c.raw)}}},scales:{y:{beginAtZero:true,grid:{color:'#edf0f3'},ticks:{callback:v=>'₹'+new Intl.NumberFormat('en-IN',{notation:'compact'}).format(v)}},x:{grid:{display:false}}}}});}
function safe(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));}
