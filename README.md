# Равномерное движение по параметрической кривой

![screenshot](./img/screenshot.png)

Траектория определяется набором точек, заданном в файле `trajectory.json`. Файл содержит массив записей, где каждая запись соответствует точке траектории. Запись содержит следующие поля: `t`-параметр от 0 до 1, и `xyz`- координаты. 

Движение объекта осуществляется в следующих вариантах:
-	ломанная линия - объект летит по прямой от одной точки до другой, параметр `t` не используется
-   кривая Безье (встроенная в `UNIGINE` реализация), постоянная скорость не выдерживается
-	[кубический сплайн](https://github.com/ttk592/spline) для каждой из координат: `x(t)`, `y(t)`, `z(t)`

-   простой ручной режим `WSAD+LShift+Space`

Установка / запуск:
```
mkdir test && cd test
wget https://github.com/xelad0m/unigine.1st.try/releases/download/v0.0.1/bundle.tar
tar -xvf bundle.tar .
./launch_release.sh
```
Проверялось:
- Alt Linux 
- UNIGINE SDK Community 2.16.1
- SDK Browser должен быть запущен 