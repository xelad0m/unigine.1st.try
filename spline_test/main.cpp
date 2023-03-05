#include <iostream>
#include <fstream>
#include <vector>
#include "spline.h"


int main() {
    const int N = 15;
    double T[N] = {0.0,0.055429223661391955,0.11226802257450681,0.16667266705943598,0.22107731154436516,0.2526429623849674,0.28730604786617,0.31645844615149604,0.34755643186681057,0.4019610763517397,0.510770365321598,0.565977087139274,0.67438162843623,0.8911907110301417,1.0};
    double X[N] = {0.0,4.0,1.0,-3.0,-6.0,-4.0,-2.0,0.0,2.0,-1.0,-9.0,-12.0,-20.0,-8.0,0.0};
    double Y[N] = {0.0,-3.0,-7.0,-4.0,-8.0,-9.5,-11.0,-12.0,-14.0,-18.0,-12.0,-16.0,-10.0,6.0,0.0};
    double Z[N] = {12.0,13.1,11.5,11.0,11.5,13.0,11.0,12.5,12.0,11.5,12.5,11.5,12.0,13.0,12.0};

    std::vector<double> t, x, y, z;
    tk::spline sx, sy, sz;

    for (int i = 0; i < N; ++i) {
        t.push_back(T[i]);
        x.push_back(X[i]);
        y.push_back(Y[i]);
        z.push_back(Z[i]);
    }
    
    // кубические сплайны со свободными крайними точками
    sx.set_boundary(tk::spline::bd_type::not_a_knot, 0.0f, tk::spline::bd_type::not_a_knot, 0.0f);
    sx.set_points(t, x);
    sy.set_boundary(tk::spline::bd_type::not_a_knot, 0.0f, tk::spline::bd_type::not_a_knot, 0.0f);
    sy.set_points(t, y);
    sz.set_boundary(tk::spline::bd_type::not_a_knot, 0.0f, tk::spline::bd_type::not_a_knot, 0.0f);
    sz.set_points(t, z);

    int n = N * 50 - 1; // 50 семплов на сегмент
    double dt = double(1) / n;

    std::ofstream out("spline.json");

    out <<     "[\n";
    for (int i = 0; i <= n; ++i) {
        out << "    {\n";
        out << "        \"t\": " << dt * i << ",\n";
        out << "        \"xyz\": [\n";
        out << "            " << sx(dt * i) << ",\n"; 
        out << "            " << sy(dt * i) << ",\n"; 
        out << "            " << sz(dt * i) << "\n";
        out << "        ]\n";
        out << "    }";
        out << ( ( i < n ) ? ",\n" : "\n" );
    }
    out <<     "]\n";

    out.close();

    return 0;
}