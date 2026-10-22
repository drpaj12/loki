module leaf(input [3:0] a, input [3:0] b, output [3:0] y);
  assign y = a - b;
endmodule

module mid(input [3:0] a, input [3:0] b, output [3:0] y);
  leaf l1(.a(a), .b(b), .y(y));
endmodule

module nested(input [3:0] a, input [3:0] b, output [3:0] y);
  mid m1(.a(a), .b(b), .y(y));
endmodule
