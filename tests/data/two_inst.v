module sub(input [3:0] a, input [3:0] b, output [3:0] y);
  assign y = a + b;
endmodule

module two_inst(input [3:0] a, input [3:0] b, input [3:0] c, output [3:0] y1, output [3:0] y2);
  sub u1(.a(a), .b(b), .y(y1));
  sub u2(.a(b), .b(c), .y(y2));
endmodule
