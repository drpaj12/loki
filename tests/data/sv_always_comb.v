module sv_always_comb(input a, input b, output logic y);
  always_comb begin
    y = a & b;
  end
endmodule
