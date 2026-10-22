module fsm2(input clk, input rst, input go, output reg busy);
  localparam IDLE = 2'd0, RUN = 2'd1, DONE = 2'd2;
  reg [1:0] state;
  always @(posedge clk) begin
    if (rst) state <= IDLE;
    else case (state)
      IDLE: if (go) state <= RUN;
      RUN: state <= DONE;
      DONE: state <= IDLE;
      default: state <= IDLE;
    endcase
  end
  always @* busy = (state == RUN);
endmodule
