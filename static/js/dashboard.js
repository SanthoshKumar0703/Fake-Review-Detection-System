document.addEventListener("DOMContentLoaded", async () => {
  const trendCanvas = document.getElementById("trendChart");
  const ratioCanvas = document.getElementById("ratioChart");
  if (!trendCanvas && !ratioCanvas) return;

  const res = await fetch("/api/stats");
  const data = await res.json();

  const teal = "#2FBFAA";
  const rust = "#E27D45";

  if (trendCanvas) {
    new Chart(trendCanvas, {
      type: "line",
      data: {
        labels: data.days.map((d) => d.slice(5)),
        datasets: [
          {
            label: "Genuine",
            data: data.genuine_series,
            borderColor: teal,
            backgroundColor: "rgba(47,191,170,0.12)",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
          },
          {
            label: "Fake",
            data: data.fake_series,
            borderColor: rust,
            backgroundColor: "rgba(226,125,69,0.12)",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { family: "Inter", size: 12 } } } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { family: "JetBrains Mono", size: 11 } } },
          y: { beginAtZero: true, ticks: { stepSize: 1, font: { family: "JetBrains Mono", size: 11 } }, grid: { color: "#F2EFE4" } },
        },
      },
    });
  }

  if (ratioCanvas) {
    const total = data.ratio.fake + data.ratio.genuine;
    new Chart(ratioCanvas, {
      type: "doughnut",
      data: {
        labels: ["Genuine", "Fake"],
        datasets: [
          {
            data: total ? [data.ratio.genuine, data.ratio.fake] : [1, 0],
            backgroundColor: [teal, rust],
            borderWidth: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "70%",
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { family: "Inter", size: 12 } } } },
      },
    });
  }
});