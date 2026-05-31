"""Generate the PWA home-screen icons (matplotlib, already installed). Run once."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

for size in (192, 512):
    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100)
    fig.patch.set_facecolor("#0b0f0e")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.5, 0.44, "↗", color="#10b981", fontsize=size * 0.5,
            ha="center", va="center", weight="bold")
    fig.savefig(f"app/icon-{size}.png", facecolor="#0b0f0e")
    plt.close(fig)
print("icons generated: app/icon-192.png, app/icon-512.png")
