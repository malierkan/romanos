import json

def fix_json_ids(input_file, output_file):
    try:
        # JSON dosyasını oku
        with open(input_file, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # Eğer data bir liste ise (senin paylaştığın formatta öyle görünüyor)
        if isinstance(data, list):
            for index, item in enumerate(data, start=1):
                item['id'] = index
            
            # Güncellenmiş veriyi yeni dosyaya yaz
            with open(output_file, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            
            print(f"İşlem başarılı! Toplam {len(data)} kayıt düzenlendi.")
            print(f"Yeni dosya: {output_file}")
        else:
            print("Hata: JSON verisi bir liste (array) formatında değil.")

    except FileNotFoundError:
        print(f"Hata: '{input_file}' dosyası bulunamadı.")
    except json.JSONDecodeError:
        print("Hata: JSON dosyası geçersiz bir formatta.")
    except Exception as e:
        print(f"Beklenmedik bir hata oluştu: {e}")

# Kullanım:
# 'veriler.json' yerine kendi dosya adını yaz
fix_json_ids('storage/posts.json', 'storage/new_posts.json')
