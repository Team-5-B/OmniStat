(() => {
  "use strict";
  const panel=document.getElementById("forecast-preview");
  if(!panel) return;
  const token=localStorage.getItem("token");
  const status=document.getElementById("forecast-preview-status");
  if(!token) { status.textContent="Sign in as the business owner to view planning forecasts."; return; }
  fetch("/api/forecast/overview?horizon=week&top=3",{
    headers:{Authorization:"Bearer "+token},cache:"no-store"
  }).then(async response=>{
    if(response.status===403) {status.textContent="Owner access is required for demand planning.";return;}
    if(!response.ok) throw new Error(`Forecast unavailable (HTTP ${response.status})`);
    const report=await response.json();
    const f=report.forecast;
    const units=document.getElementById("forecast-preview-units");
    const range=document.getElementById("forecast-preview-range");
    if(f.status!=="ready"){
      status.textContent=`Need ${f.minimum_history_days} calendar days and ${f.minimum_active_days} active days; currently ${f.history_span_days} / ${f.active_sales_days}.`;
      units.textContent="More data needed";
      range.textContent="—";
      return;
    }
    const nf=new Intl.NumberFormat("en-US",{maximumFractionDigits:1});
    units.textContent=nf.format(f.totals.expected_net_units)+" units";
    range.textContent=nf.format(f.totals.unit_planning_range_low)+"–"+nf.format(f.totals.unit_planning_range_high)+" units";
    status.textContent="Historical baseline · next 7 days · review data-quality alerts before ordering";
  }).catch(err=>{status.textContent=err.message || "Unable to load forecast.";});
})();
