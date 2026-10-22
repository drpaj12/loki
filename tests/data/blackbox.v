(* blackbox *)
module bb(input a, output y);
endmodule

module blackbox(input a, output y);
  bb u0(.a(a), .y(y));
endmodule
