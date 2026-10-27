module top(input a, input b, input c, input d, output y2, output z);
  wire y1;
  wire dead;
  assign y1 = a & b;
  assign y2 = y1 | c;
  assign dead = a ^ d;
  assign z = c;
endmodule
