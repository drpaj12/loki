module child(input a, input b, output y);
  assign y = a & b;
endmodule

module top(input a, input b, input c, output z);
  wire w;
  child u0(.a(a), .b(b), .y(w));
  assign z = w | c;
endmodule
