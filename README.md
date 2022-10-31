# Skarnik vocabulary downloader | for Skarnik iOS

main.py - гэта генератар sqlite базы данных [vocabulary.db](https://github.com/belanghelp/skarnik.by-ios/blob/main/Skarnik/vocabulary.db) для iOS аплікацыі [Skarnik for iOS](https://github.com/belanghelp/skarnik.by-ios).


Скрыпт спампоўвае спіс слоў з іх ідэнтыфікатарам са [skarnik.by](https://skarnik.by) для трох слоўнікаў:
* Руска-Беларускі
* Беларуска-Рускі
* Беларускі тлумачальны

Пасля спампоўвання слоў, скрыпт дадае іх ў базу данных і індэксуе для хуткага пошуку ў аплікацыі.

> Скрыпт трэба было зрабіць, каб час ад часу запускаць, абнаўляць базу са спісам новых слоў і выпускаць абнаўленне iOS аплікацыі, бо часова немагчыма інтэграваць аўтаматычную спампоўку спіса слоў са скарніка адразу ў аплікацыі.
