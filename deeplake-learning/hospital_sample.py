from pathlib import Path
import deeplake

dataset_path = str(Path(__file__).parent/"hospital_sample")

if deeplake.exists(dataset_path):
    ds = deeplake.open(dataset_path)
else:
    ds = deeplake.create(dataset_path)
    ds.add_column("ccn", deeplake.types.Text())
    ds.add_column("drg", deeplake.types.Text())
    ds.add_column("avg_charges", deeplake.types.Float64())

ds.commit()
ds.summary()

# Synthetic values
ds.append([
    {
        "ccn": "010001",
        "drg": "871",
        "avg_charges": 25000.0,
    }
])

ds.commit()

saved = deeplake.open_read_only(dataset_path)
saved.summary()

print("Saved CCN:", saved["ccn"][0])